from fastapi import FastAPI, Depends, HTTPException
from database import engine, get_db
from models import Base, User
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from auth import create_access_token, get_current_user
from schemas import LoginRequest, RegisterRequest

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
