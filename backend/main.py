from fastapi import FastAPI, Depends, HTTPException
from database import engine, get_db
from models import Base, User, Connection 
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from auth import create_access_token, get_current_user
from schemas import LoginRequest, RegisterRequest, ConnectionsRequest
from sqlalchemy import or_

app = FastAPI()

Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.get("/")
def root():
    return {"message": "Six Degrees API running"}

@app.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(request.password)

    user = User(
        full_name= request.full_name,
        email= request.email,
        password_hash= hashed_password,
        linkedin_slug= request.linkedin_slug.lower()
    )

    db.add(user)
    db.commit()
    db.refresh(user)

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
    target_user = db.query(User).filter(User.linkedin_slug == request.linkedin_slug.lower()).first()
    if not(target_user):
        raise HTTPException(status_code=404, detail="User not found")
    if (target_user.id == current_user.id):
        raise HTTPException(status_code=400, detail="Cannot connect with yourself")
    a = min(current_user.id, target_user.id)
    b = max(current_user.id, target_user.id)

    if (db.query(Connection).filter(Connection.user_id_1 == a, Connection.user_id_2 == b).first()):
        return {"message": "Connection already exists"}
    
    connection = Connection (
        user_id_1 = a,
        user_id_2 = b,
    )

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

