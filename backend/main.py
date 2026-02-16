from fastapi import FastAPI, Depends, HTTPException
from database import engine, get_db
from models import Base, User
from sqlalchemy.orm import Session
from passlib.context import CryptContext

app = FastAPI()

Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.get("/")
def root():
    return {"message": "Six Degrees API running"}

@app.post("/register")
def register(full_name: str, email: str, password: str, linkedin_slug: str, db: Session = Depends(get_db)):
    
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(password)

    user = User(
        full_name=full_name,
        email=email,
        password_hash=hashed_password,
        linkedin_slug=linkedin_slug.lower()
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "User created successfully"}
