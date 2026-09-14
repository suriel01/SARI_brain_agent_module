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
    can_create_chats: bool = False
    can_delete_chats: bool = False
    can_rename_chats: bool = False
    can_control_hardware: bool = False
    can_manage_users: bool = False

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
    snapshot: Optional[str] = None

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
    language: Optional[str] = "es"

# --- Eye Nodes ---
class EyeNodeBase(BaseModel):
    node_id: str
    name: str
    ip: Optional[str] = "192.168.1.73"
    stream_url: Optional[str] = "http://192.168.55.1:8080/mjpeg"
    yolo_threshold: Optional[float] = 0.70
    is_active: Optional[bool] = True

class EyeNodeCreate(EyeNodeBase):
    pass

class EyeNodeUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    stream_url: Optional[str] = None
    yolo_threshold: Optional[float] = None
    is_active: Optional[bool] = None
    pin: Optional[str] = None

class EyeNodeResponse(EyeNodeBase):
    id: int
    created_at: datetime
    is_online: Optional[bool] = False
    fps: Optional[float] = 0.0
    ram_used_gb: Optional[float] = None
    ram_total_gb: Optional[float] = None
    cpu_load_pct: Optional[float] = None
    gpu_load_pct: Optional[float] = None
    temp_c: Optional[float] = None
    link_status: Optional[str] = None
    tracking_enabled: Optional[bool] = True
    class Config:
        from_attributes = True

class TestConnectionRequest(BaseModel):
    target_url: str
