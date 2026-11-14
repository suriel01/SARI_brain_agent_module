"""In-memory failure counters for login and PIN brute-force protection.

A key (account, client IP, user, Telegram chat) that accumulates `max_failures` failures
inside `window_seconds` is locked for `lockout_seconds`. State lives in this process only,
which is enough for the single backend container; a restart clears it.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

# Injectable clock (monotonic seconds); tests replace it.
clock = time.monotonic

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
LOCKOUT_SECONDS = 15 * 60


class RateLimited(Exception):
    """Raised when a key is locked out."""


class FailureLimiter:
    def __init__(self, max_failures: int = MAX_FAILURES, window_seconds: float = WINDOW_SECONDS,
                 lockout_seconds: float = LOCKOUT_SECONDS):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._failures: Dict[str, Deque[float]] = defaultdict(deque)
        self._locked_until: Dict[str, float] = {}
        self._lock = threading.Lock()

    def is_locked(self, key: str) -> bool:
        now = clock()
        with self._lock:
            until = self._locked_until.get(key)
            if until is None:
                return False
            if now >= until:
                del self._locked_until[key]
                return False
            return True

    def record_failure(self, key: str) -> None:
        now = clock()
        with self._lock:
            failures = self._failures[key]
            failures.append(now)
            while failures and now - failures[0] > self.window_seconds:
                failures.popleft()
            if len(failures) >= self.max_failures:
                self._locked_until[key] = now + self.lockout_seconds
                failures.clear()

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()
            self._locked_until.clear()


login_limiter = FailureLimiter()
pin_limiter = FailureLimiter()


def reset_all() -> None:
    login_limiter.clear()
    pin_limiter.clear()
