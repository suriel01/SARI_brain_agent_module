from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import jwt
from datetime import datetime, timedelta
from ..database import get_db
from ..crud import crud
from ..schemas import schemas

router = APIRouter()

SECRET_KEY = "SARI_SUPER_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

@router.post("/login", response_model=schemas.Token)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, req.username)
    if not user or not crud.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": user.username,
        "username": user.username,
        "role": user.role,
        "exp": expires,
        "id": user.id,
        "clearance_level": user.clearance_level,
        "can_create_chats": user.can_create_chats or (user.role == "admin"),
        "can_delete_chats": user.can_delete_chats or (user.role == "admin"),
        "can_rename_chats": user.can_rename_chats or (user.role == "admin"),
        "can_control_hardware": user.can_control_hardware or (user.role == "admin"),
        "can_manage_users": user.can_manage_users or (user.role == "admin")
    }
    access_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    
    from .hardware import HardwareState
    HardwareState.add_log(f"🔑 User [{user.username}] ({user.role.upper()}) logged in successfully", level="INFO", camera_module="AUTH_SYS")

    return {"access_token": access_token, "token_type": "bearer", "role": user.role}
