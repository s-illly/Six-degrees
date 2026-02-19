from fastapi import FastAPI, Depends, HTTPException
from database import engine, get_db
from models import Base, User, Connection, GhostProfile, GhostEdge
from sqlalchemy.orm import Session
from auth import get_current_user
from auth import router as auth_router
from schemas import ConnectionsRequest, ClaimSlugRequest
from sqlalchemy import or_
from collections import defaultdict, deque 
from fastapi.middleware.cors import CORSMiddleware
from linkedin_utils import normalize_linkedin_slug, find_ghost_profiles_for_slug, migrate_ghost_edges_to_user

app = FastAPI()
app.include_router(auth_router)

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def root():
    return {"message": "Six Degrees API running"}

@app.get("/users")
def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "linkedin_slug": u.linkedin_slug,
        }
        for u in users
    ]

@app.get("/graph/all")
def graph_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    edges = db.query(Connection).all()

    nodes = [
        {
            "id": u.id,
            "type": "user",
            "label": u.full_name,
            "linkedin_slug": u.linkedin_slug,
        }
        for u in users
    ]

    graph_edges = [
        {
            "source": e.user_id_1,
            "target": e.user_id_2,
            "type": "connection",
        }
        for e in edges
    ]

    # Include current user's pending edges to unregistered (ghost) profiles.
    pending_edges = db.query(GhostEdge).filter(GhostEdge.src_user_id == current_user.id).all()
    ghost_ids = {pe.ghost_id for pe in pending_edges}
    ghosts = []
    if ghost_ids:
        ghosts = db.query(GhostProfile).filter(GhostProfile.id.in_(list(ghost_ids))).all()

    for g in ghosts:
        nodes.append(
            {
                "id": g.id,
                "type": "ghost",
                "label": g.full_name or g.linkedin_slug,
                "linkedin_slug": g.linkedin_slug,
            }
        )

    for pe in pending_edges:
        graph_edges.append(
            {
                "source": pe.src_user_id,
                "target": pe.ghost_id,
                "type": "pending",
            }
        )

    return {"nodes": nodes, "edges": graph_edges}

@app.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/me/slug")
def claim_slug(request: ClaimSlugRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slug = normalize_linkedin_slug(request.linkedin_slug)
    if not slug:
        raise HTTPException(status_code=400, detail="Linkedin is required")
    
    existing_owner = (db.query(User).filter(User.linkedin_slug == slug, User.id != current_user.id)).first()
    if existing_owner:
        raise HTTPException(status_code=400, detail="Linkedin account claimed")
    
    current_user.linkedin_slug = slug 
    db.add(current_user)
    migrated = migrate_ghost_edges_to_user(db, current_user, slug)
    db.commit()
    db.refresh(current_user)

    if migrated:
        return {"message": "Linkedin claimed + ghost migrated", "linkedin_slug": slug, "migrated": migrated}
    return {"message": "Linkedin claimed", "linkedin_slug": slug, "migrated": 0}


@app.post("/connections")
def add_connections(request: ConnectionsRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slug = normalize_linkedin_slug(request.linkedin_slug)
    if not slug:
        raise HTTPException(status_code=400, detail="Linkedin is required")
    target_user = db.query(User).filter(User.linkedin_slug == slug).first()
    
    # target is unregistered -> ghost profile 
    if not(target_user):
        ghosts = find_ghost_profiles_for_slug(db, slug)
        ghost = ghosts[0] if ghosts else None
        if not(ghost):
            ghost = GhostProfile(linkedin_slug = slug)

            db.add(ghost)
            db.commit()
            db.refresh(ghost)

        existing_edge = (db.query(GhostEdge).filter(GhostEdge.src_user_id == current_user.id, GhostEdge.ghost_id == ghost.id).first())
        if existing_edge:
            return {"message": "Connection already exists"}

        pending = GhostEdge(src_user_id = current_user.id, ghost_id = ghost.id)
        db.add(pending)
        db.commit()

        return {"message": "Pending connection created", "to": slug}

    # target exists -> create real connection 
    if (target_user.id == current_user.id):
        raise HTTPException(status_code=400, detail="Cannot connect with yourself")
    a = min(current_user.id, target_user.id)
    b = max(current_user.id, target_user.id)

    if (db.query(Connection).filter(Connection.user_id_1 == a, Connection.user_id_2 == b).first()):
        return {"message": "Connection already exists"}
    
    connection = Connection (user_id_1 = a, user_id_2 = b)

    db.add(connection)
    db.commit()
    db.refresh(connection)

    return {"message": "connected", "to": target_user.linkedin_slug}



@app.get("/connections")
def get_connections(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    edges = db.query(Connection).filter(or_(Connection.user_id_1 == current_user.id, Connection.user_id_2 == current_user.id)).all()
    other_ids = set()
    for edge in edges:
        if edge.user_id_1 == current_user.id:
            other_ids.add(edge.user_id_2)
        else:
            other_ids.add(edge.user_id_1)
    
    if not other_ids:
        return []
    users = db.query(User).filter(User.id.in_(list(other_ids))).all()

    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "linkedin_slug": u.linkedin_slug
        }
        for u in users
    ]


@app.get("/search")
def degree(linkedin_slug: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target_slug = normalize_linkedin_slug(linkedin_slug)
    target_user = db.query(User).filter(User.linkedin_slug == target_slug).first()
    if not(target_user):
        raise HTTPException(status_code=404, detail="User not found")
    
    edges = db.query(Connection).all()
    adj = defaultdict(list)

    for e in edges:
        adj[e.user_id_1].append(e.user_id_2)
        adj[e.user_id_2].append(e.user_id_1)

    start = current_user.id 
    goal = target_user.id 

    queue = deque([start])
    visited = set([start])
    prev = {start: None}

    while queue:
        node = queue.popleft()

        if node == goal:
            break
        for nei in adj.get(node, []):
            if nei not in visited:
                visited.add(nei)
                prev[nei] = node 
                queue.append(nei)
    
    if goal not in prev: 
        return {"degrees": None, "path": []}    
    path_ids = []
    cur = goal
    while cur is not None:
        path_ids.append(cur)
        cur = prev[cur]
    path_ids.reverse()
    degrees = len(path_ids) - 1

    users = db.query(User).filter(User.id.in_(path_ids)).all()
    by_id = {u.id: u for u in users}

    path = [
        {
            "id": uid,
            "full_name": by_id[uid].full_name,
            "linkedin_slug": by_id[uid].linkedin_slug,
        }
        for uid in path_ids
    ]
    return {"degrees": degrees, "path": path}


@app.get("/search/id")
def degree_by_id(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target_id = (user_id or "").strip()
    if not target_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    target_user = db.query(User).filter(User.id == target_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    edges = db.query(Connection).all()
    adj = defaultdict(list)

    for e in edges:
        adj[e.user_id_1].append(e.user_id_2)
        adj[e.user_id_2].append(e.user_id_1)

    start = current_user.id
    goal = target_user.id

    queue = deque([start])
    visited = set([start])
    prev = {start: None}

    while queue:
        node = queue.popleft()

        if node == goal:
            break
        for nei in adj.get(node, []):
            if nei not in visited:
                visited.add(nei)
                prev[nei] = node
                queue.append(nei)

    if goal not in prev:
        return {"degrees": None, "path": []}

    path_ids = []
    cur = goal
    while cur is not None:
        path_ids.append(cur)
        cur = prev[cur]
    path_ids.reverse()
    degrees = len(path_ids) - 1

    users = db.query(User).filter(User.id.in_(path_ids)).all()
    by_id = {u.id: u for u in users}

    path = [
        {
            "id": uid,
            "full_name": by_id[uid].full_name,
            "linkedin_slug": by_id[uid].linkedin_slug,
        }
        for uid in path_ids
    ]
    return {"degrees": degrees, "path": path}

@app.get("/graph")
def graph(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conn_edges = (db.query(Connection).filter(or_(Connection.user_id_1 == current_user.id, Connection.user_id_2 == current_user.id))).all()
    connected_user_ids = set()
    for e in conn_edges:
        other = e.user_id_2 if e.user_id_1 == current_user.id else e.user_id_1
        connected_user_ids.add(other)  
    connected_users = []
    if connected_user_ids:
        connected_users = db.query(User).filter(User.id.in_(list(connected_user_ids))).all()

    pending_edges = db.query(GhostEdge).filter(GhostEdge.src_user_id == current_user.id).all()
    ghost_ids = {pe.ghost_id for pe in pending_edges}
    ghosts = []
    if ghost_ids:
        ghosts = db.query(GhostProfile).filter(GhostProfile.id.in_(list(ghost_ids))).all()

    nodes = []
    # current user node
    nodes.append({
        "id": current_user.id,
        "type": "user",
        "label": current_user.full_name,
        "linkedin_slug": current_user.linkedin_slug
    })

    # neighbour user nodes
    for u in connected_users: 
        nodes.append({
            "id": u.id,
            "type": "user",
            "label": u.full_name,
            "linkedin_slug": u.linkedin_slug,
        })

    # ghost nodes
    for g in ghosts:
        nodes.append({
            "id": g.id,
            "type": "ghost",
            "label": g.full_name or g.linkedin_slug,
            "linkedin_slug": g.linkedin_slug,
        })

     
    edges = []
    # user -> user
    for e in conn_edges:
        a = e.user_id_1
        b = e.user_id_2 
        edges.append({
            "source": a,
            "target": b,
            "type": "connection",
        })
    
    # current_user -> ghost 
    for pe in pending_edges:
        edges.append({
            "source": pe.src_user_id,
            "target": pe.ghost_id,
            "type": "pending",
        })

    return {"nodes": nodes, "edges": edges}
