from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from src.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    pref_max_detour = Column(Integer, nullable=False, default=30, server_default="30")
    pref_mode = Column(String(10), nullable=False, default="sun", server_default="sun")
    pref_map_controls = Column(Boolean, nullable=False, default=False, server_default="0")
    pref_map_type = Column(String(20), nullable=False, default="roadmap", server_default="roadmap")

    routes = relationship("Route", back_populates="user")
    spots = relationship("Spot", back_populates="user")
    feedback = relationship("Feedback", back_populates="user")


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    start_lat = Column(Float, nullable=False)
    start_lng = Column(Float, nullable=False)
    end_lat = Column(Float, nullable=False)
    end_lng = Column(Float, nullable=False)
    start_address = Column(String(512), nullable=True)
    end_address = Column(String(512), nullable=True)
    preference = Column(String(10), nullable=True)
    share_token = Column(String(36), nullable=True, unique=True, index=True)
    route_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="routes")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="feedback")


class Spot(Base):
    __tablename__ = "spots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String(512), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    icon = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    place_id = Column(String(255), nullable=True)
    city = Column(String(255), nullable=False, server_default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    share_token = Column(String(36), nullable=True, unique=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="spots")
