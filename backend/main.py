from fastapi import FastAPI, Depends, HTTPException
from database import engine, get_db
from models import Base, User, Connection, GhostProfile, GhostEdge
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from auth import create_access_token, get_current_user
from schemas import LoginRequest, RegisterRequest, ConnectionsRequest
from sqlalchemy import or_
from collections import defaultdict, deque 

app = FastAPI()

Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.get("/")
def root():
    return {"message": "Six Degrees API running"}

@app.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    slug = request.linkedin_slug.strip().lower()
    
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(request.password)

    user = User(
        full_name= request.full_name,
        email= request.email,
        password_hash= hashed_password,
        linkedin_slug= slug 
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Create user from ghost profile 
    existing_ghost = db.query(GhostProfile).filter(GhostProfile.linkedin_slug == slug).first()
    if existing_ghost:
        pending_edges = db.query(GhostEdge).filter(GhostEdge.ghost_id == existing_ghost.id).all()

        for pe in pending_edges:
            a = min(pe.src_user_id, user.id)
            b = max(pe.src_user_id, user.id)

            exists = db.query(Connection).filter(Connection.user_id_1 == a, Connection.user_id_2 == b).first()
            if not(exists):
                db.add(Connection(user_id_1 = a, user_id_2 = b))
        
        for pe in pending_edges:
            db.delete(pe)
        db.delete(existing_ghost)
        db.commit()

    return {"message": "User created successfully"}

@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == request.email).first()
    if not(existing_user):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not(pwd_context.verify(request.password, existing_user.password_hash)):
        raise HTTPException(status_code=401, detail="Incorrect password")
    
    token = create_access_token({"email": existing_user.email})
    return {
        "access_token": token,
        "token_type": "bearer"
    }

@app.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/connections")
def add_connections(request: ConnectionsRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slug = request.linkedin_slug.strip().lower()
    target_user = db.query(User).filter(User.linkedin_slug == slug).first()
    
    # target is unregistered -> ghost profile 
    if not(target_user):
        ghost = db.query(GhostProfile).filter(GhostProfile.linkedin_slug == slug).first()
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
            "full_name": u.full_name,
            "linkedin_slug": u.linkedin_slug
        }
        for u in users
    ]


@app.get("/search")
def degree(linkedin_slug: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target_slug = linkedin_slug.strip().lower()
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
            "full_name": by_id[uid].full_name,
            "linkedin_slug": by_id[uid].linkedin_slug,
        }
        for uid in path_ids
    ]
    return {"degrees": degrees, "path": path}
