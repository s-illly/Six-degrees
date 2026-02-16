from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
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

class Connection(Base):
    __tablename__ = "connections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id_1 = Column(String, ForeignKey("users.id"), nullable=False)
    user_id_2 = Column(String, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id_1", "user_id_2", name="unique_connection"),
    )
