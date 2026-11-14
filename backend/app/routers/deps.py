from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from ..security import SECRET_KEY, ALGORITHM, has_perm

security = HTTPBearer()


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


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return decode_token(credentials.credentials)


def require_hardware_user(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_perm(current_user, "can_control_hardware"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user
