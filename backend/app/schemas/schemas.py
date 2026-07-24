from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

# --- Users ---
class UserBase(BaseModel):
    username: str
    role: str
    clearance_level: int
    can_create_chats: Optional[bool] = False
    can_delete_chats: Optional[bool] = False
    can_rename_chats: Optional[bool] = False
    can_control_hardware: Optional[bool] = False
    can_manage_users: Optional[bool] = False

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    class Config:
        orm_mode = True

# --- Chat Messages ---
class ChatMessageBase(BaseModel):
    role: str
    content: str

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessageResponse(ChatMessageBase):
    id: int
    timestamp: datetime
    class Config:
        orm_mode = True

# --- Chat Threads ---
class ChatThreadBase(BaseModel):
    title: str

class ChatThreadCreate(ChatThreadBase):
    pin: Optional[str] = None

class ChatThreadResponse(ChatThreadBase):
    id: int
    created_at: datetime
    messages: List[ChatMessageResponse] = []
    class Config:
        orm_mode = True

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[int] = None
    pin: Optional[str] = None
