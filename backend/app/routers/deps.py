from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
from ..database import SessionLocal, get_db
from ..models import models
from ..security import SECRET_KEY, ALGORITHM, has_perm

security = HTTPBearer()

PERMISSION_FLAGS = (
    "can_create_chats",
    "can_delete_chats",
    "can_rename_chats",
    "can_control_hardware",
    "can_manage_users",
)


def decode_token(token: str) -> dict:
    """Validates a JWT (signature and expiry) and returns its payload, or raises 401."""
    if not token:
        raise HTTPException(status_code=401, detail="Token ausente")
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], leeway=30)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def load_current_user(payload: dict, db: Session) -> dict:
    """Returns the user's CURRENT role and permissions from the DB; the token only proves identity."""
    user = db.get(models.User, payload.get("id")) if payload.get("id") is not None else None
    if user is None or user.username != payload.get("sub"):
        raise HTTPException(status_code=401, detail="Usuario no válido")
    is_admin = user.role == "admin"
    return {
        "sub": user.username,
        "username": user.username,
        "role": user.role,
        "id": user.id,
        "clearance_level": user.clearance_level,
        "exp": payload.get("exp"),
        **{flag: bool(getattr(user, flag) or is_admin) for flag in PERMISSION_FLAGS},
    }


def authenticate_token(token: str) -> dict:
    """Token check for channels without dependency injection (WebSocket)."""
    payload = decode_token(token)
    db = SessionLocal()
    try:
        return load_current_user(payload, db)
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    return load_current_user(decode_token(credentials.credentials), db)


def require_hardware_user(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_perm(current_user, "can_control_hardware"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user
