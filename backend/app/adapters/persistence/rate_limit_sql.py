"""Failure-counter store for `app.ratelimit.FailureLimiter` on the application database.

Table from Alembic revision ``0003_rate_limits``. Each change runs under a row lock
(``SELECT ... FOR UPDATE`` on PostgreSQL), so failures recorded by different API workers for the
same key are never lost and the lockout is seen by every worker.
"""
from typing import Callable, List, Optional, Tuple

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models.models import RateLimitRow

Counters = Tuple[List[float], Optional[float]]


class SqlFailureStore:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def read(self, key: str) -> Counters:
        with self._session_factory() as session:
            row = session.get(RateLimitRow, key)
            if row is None:
                return [], None
            return list(row.failures or []), row.locked_until

    def update(self, key: str, change: Callable[[List[float], Optional[float]], Counters]) -> None:
        """Applies ``change(failures, locked_until)`` atomically and stores its result."""
        for attempt in (1, 2):
            with self._session_factory() as session:
                row = session.get(RateLimitRow, key, with_for_update=True)
                failures, locked_until = change(list(row.failures or []) if row else [], row.locked_until if row else None)
                if row is None:
                    session.add(RateLimitRow(key=key, failures=list(failures), locked_until=locked_until))
                else:
                    row.failures = list(failures)
                    row.locked_until = locked_until
                try:
                    session.commit()
                    return
                except IntegrityError:
                    session.rollback()  # created concurrently: retry as an update
                    if attempt == 2:
                        raise

    def delete(self, key: str) -> None:
        with self._session_factory() as session:
            session.execute(delete(RateLimitRow).where(RateLimitRow.key == key))
            session.commit()

    def delete_prefix(self, prefix: str) -> None:
        with self._session_factory() as session:
            session.execute(delete(RateLimitRow).where(RateLimitRow.key.startswith(prefix, autoescape=True)))
            session.commit()
