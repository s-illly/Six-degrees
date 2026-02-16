from sqlalchemy import Column, String
from sqlalchemy.dialects.sqlite import BLOB
import uuid

from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    linkedin_slug = Column(String, unique=True, index=True, nullable=False)
