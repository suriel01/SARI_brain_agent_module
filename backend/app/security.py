import os
from typing import Optional

from fastapi import HTTPException

SECRET_KEY = os.environ.get("SARI_SECRET_KEY", "SARI_SUPER_SECRET_KEY")
ALGORITHM = "HS256"
SECURITY_PIN = os.environ.get("SARI_SECURITY_PIN", "1234")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("SARI_TOKEN_EXPIRE_MINUTES", "720"))


def is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


def has_perm(user: dict, flag: str) -> bool:
    return is_admin(user) or bool(user.get(flag))


def require_pin(pin: Optional[str]) -> None:
    if pin != SECURITY_PIN:
        raise HTTPException(status_code=401, detail="PIN de seguridad inválido")
