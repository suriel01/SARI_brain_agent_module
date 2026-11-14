"""Failure counters for login and PIN brute-force protection.

A key (account, client IP, user, Telegram chat) that accumulates `max_failures` failures
inside `window_seconds` is locked for `lockout_seconds`. Counters live in the application
database (`SqlFailureStore`, table `rate_limit`), so a lockout holds across every API worker,
the background worker and restarts. `MemoryFailureStore` keeps them in this process only.
"""
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

# Injectable clock (wall-clock seconds, since counters are shared and persisted); tests replace it.
clock = time.time

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
LOCKOUT_SECONDS = 15 * 60

Counters = Tuple[List[float], Optional[float]]


class RateLimited(Exception):
    """Raised when a key is locked out."""


class MemoryFailureStore:
    """Process-local counters (tests and single-process tools)."""

    def __init__(self):
        self._rows: Dict[str, Counters] = {}
        self._lock = threading.Lock()

    def read(self, key: str) -> Counters:
        with self._lock:
            failures, locked_until = self._rows.get(key, ([], None))
            return list(failures), locked_until

    def update(self, key: str, change: Callable[[List[float], Optional[float]], Counters]) -> None:
        with self._lock:
            failures, locked_until = self._rows.get(key, ([], None))
            self._rows[key] = change(list(failures), locked_until)

    def delete(self, key: str) -> None:
        with self._lock:
            self._rows.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in [k for k in self._rows if k.startswith(prefix)]:
                del self._rows[key]


def _default_store():
    from .adapters.persistence.rate_limit_sql import SqlFailureStore
    from .database import SessionLocal

    return SqlFailureStore(SessionLocal)


class FailureLimiter:
    def __init__(self, max_failures: int = MAX_FAILURES, window_seconds: float = WINDOW_SECONDS,
                 lockout_seconds: float = LOCKOUT_SECONDS, *, scope: str = "default", store=None):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self.scope = scope
        self._store = store if store is not None else _default_store()

    def _key(self, key: str) -> str:
        return f"{self.scope}:{key}"

    def is_locked(self, key: str) -> bool:
        _failures, locked_until = self._store.read(self._key(key))
        return locked_until is not None and clock() < locked_until

    def record_failure(self, key: str) -> None:
        now = clock()

        def change(failures: List[float], locked_until: Optional[float]) -> Counters:
            failures = [t for t in failures if now - t <= self.window_seconds] + [now]
            if len(failures) >= self.max_failures:
                return [], now + self.lockout_seconds
            return failures, locked_until

        self._store.update(self._key(key), change)

    def reset(self, key: str) -> None:
        self._store.delete(self._key(key))

    def clear(self) -> None:
        self._store.delete_prefix(f"{self.scope}:")


login_limiter = FailureLimiter(scope="login")
pin_limiter = FailureLimiter(scope="pin")


def reset_all() -> None:
    login_limiter.clear()
    pin_limiter.clear()
