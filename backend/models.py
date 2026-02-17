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

class GhostProfile(Base):
    __tablename__ = "ghost_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    linkedin_slug = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    #created_by_user_id = Column(String, ForeignKey("users.id"))

class GhostEdge(Base):
    __tablename__ = "pending_edges"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    src_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    ghost_id = Column(String, ForeignKey("ghost_profiles.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("src_user_id", "ghost_id", name="unique_pending_edge"),
    )
