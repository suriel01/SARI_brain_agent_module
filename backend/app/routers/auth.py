from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import jwt
from datetime import datetime, timedelta, timezone
from ..database import get_db
from ..crud import crud
from ..schemas import schemas
from ..security import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

@router.post("/login", response_model=schemas.Token)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, req.username)
    if not user or not crud.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    is_admin = user.role == "admin"
    perms = {
        "can_create_chats": bool(user.can_create_chats or is_admin),
        "can_delete_chats": bool(user.can_delete_chats or is_admin),
        "can_rename_chats": bool(user.can_rename_chats or is_admin),
        "can_control_hardware": bool(user.can_control_hardware or is_admin),
        "can_manage_users": bool(user.can_manage_users or is_admin),
    }
    token_data = {
        "sub": user.username,
        "username": user.username,
        "role": user.role,
        "exp": expires,
        "id": user.id,
        "clearance_level": user.clearance_level,
        **perms,
    }
    access_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    
    from .hardware import HardwareState
    HardwareState.add_log(f"🔑 User [{user.username}] ({user.role.upper()}) logged in successfully", level="INFO", camera_module="AUTH_SYS")

    return {"access_token": access_token, "token_type": "bearer", "role": user.role, **perms}
