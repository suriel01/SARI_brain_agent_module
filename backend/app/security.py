import hmac
from typing import Optional

from fastapi import HTTPException

from .config import get_settings

_settings = get_settings()

SECRET_KEY = _settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _settings.token_expire_minutes


def is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


def has_perm(user: dict, flag: str) -> bool:
    return is_admin(user) or bool(user.get(flag))


def pin_matches(pin: Optional[str]) -> bool:
    if not pin:
        return False
    return hmac.compare_digest(str(pin).encode(), get_settings().security_pin.encode())


def require_pin(pin: Optional[str]) -> None:
    if not pin_matches(pin):
        raise HTTPException(status_code=401, detail="PIN de seguridad inválido")
