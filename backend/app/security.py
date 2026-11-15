import hmac
from typing import Optional

from fastapi import HTTPException

from .config import get_settings
from .domain.actors import has_permission
from .ratelimit import RateLimited, pin_limiter

_settings = get_settings()

SECRET_KEY = _settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _settings.token_expire_minutes


def is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


def has_perm(user: dict, flag: str) -> bool:
    """HTTP-side name for the domain permission rule (admins hold every permission)."""
    return has_permission(user, flag)


def pin_matches(pin: Optional[str]) -> bool:
    if not pin:
        return False
    return hmac.compare_digest(str(pin).encode(), get_settings().security_pin.encode())


def check_pin(pin: Optional[str], key: Optional[str] = None) -> bool:
    """Constant-time PIN check. With a `key` (user, chat) wrong guesses count toward a lockout.

    Raises RateLimited while `key` is locked out, even for the right PIN.
    """
    if key and pin_limiter.is_locked(key):
        raise RateLimited(key)
    ok = pin_matches(pin)
    if key:
        if ok:
            pin_limiter.reset(key)
        elif pin:
            pin_limiter.record_failure(key)
    return ok


def require_pin(pin: Optional[str], key: Optional[str] = None) -> None:
    try:
        ok = check_pin(pin, key)
    except RateLimited:
        raise HTTPException(status_code=429, detail="Demasiados intentos de PIN. Intenta más tarde.")
    if not ok:
        raise HTTPException(status_code=401, detail="PIN de seguridad inválido")
