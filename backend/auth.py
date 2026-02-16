from jwt import ExpiredSignatureError, InvalidTokenError
import jwt 
import datetime
import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User

load_dotenv()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_access_token(data: dict):
    payload = {
        "sub": data["email"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
    }

    token = jwt.encode(
        payload = payload,
        key = os.getenv("SECRET_KEY"),
        algorithm = os.getenv("ALGORITHM")
    )

    return token


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, key = os.getenv("SECRET_KEY"), algorithms = os.getenv("ALGORITHM"))
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code = 401, detail = "Invalid token")
        user = db.query(User).filter(User.email == email.lower()).first()
        if user is None:
            raise HTTPException(status_code = 401, detail = "User not found")
        return user
    except ExpiredSignatureError:
        raise HTTPException(status_code = 401, detail = "Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code = 401, detail = "Invalid token")
    