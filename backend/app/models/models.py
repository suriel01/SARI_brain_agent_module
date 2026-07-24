from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), default="monitor")
    clearance_level = Column(Integer, default=1)

    can_create_chats = Column(Boolean, default=False)
    can_delete_chats = Column(Boolean, default=False)
    can_rename_chats = Column(Boolean, default=False)
    can_control_hardware = Column(Boolean, default=False)
    can_manage_users = Column(Boolean, default=False)

    threads = relationship("ChatThread", back_populates="user", cascade="all, delete-orphan")

class ChatThread(Base):
    __tablename__ = "chat_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(100), default="Nueva Conversación")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="threads")
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id"))
    role = Column(String(20)) # "user", "system", "agent"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    thread = relationship("ChatThread", back_populates="messages")
