"""StateRepository on the application database (PostgreSQL in production, SQLite in unit tests).

Tables come from Alembic revision ``0002_runtime_state``. Every method opens its own short session,
so the state is shared by all API workers and survives a restart.
"""
import datetime
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...domain.state import (
    LOG_CAPACITY, LOG_TIME_FORMAT, LOG_TTL_HOURS, RUNTIME_FIELDS, ActuatorState, RuntimeState, new_node,
)
from ...models.models import ActuatorStateRow, NodeStatus, OperationalLog

ROW_ID = 1


def _last_seen(data: Dict[str, Any]) -> Optional[float]:
    value = data.get("last_seen")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _log_dict(row: OperationalLog) -> Dict[str, Any]:
    return {
        "timestamp": row.created_at.strftime(LOG_TIME_FORMAT),
        "message": row.message,
        "level": row.level,
        "camera_module": row.camera_module,
        "expires_at": row.expires_at.strftime(LOG_TIME_FORMAT),
    }


class SqlStateRepository:
    def __init__(self, session_factory: Callable[[], Session], clock: Callable[[], float] = time.time):
        self._session_factory = session_factory
        self._clock = clock

    # -- actuators and counters -------------------------------------------------------------
    def _ensure_row(self, session: Session) -> None:
        if session.get(ActuatorStateRow, ROW_ID) is not None:
            return
        try:
            with session.begin_nested():
                session.add(ActuatorStateRow(id=ROW_ID, siren_active=False, gates_locked=False, alert_count=0,
                                             last_alert_time=0.0, last_alert_thread_id=None))
        except IntegrityError:
            pass  # another process created it first

    def _update_row(self, *, where=None, **values) -> int:
        """One UPDATE on the actuator row (created on first use); returns the number of rows changed."""
        with self._session_factory() as session:
            self._ensure_row(session)
            stmt = update(ActuatorStateRow).where(ActuatorStateRow.id == ROW_ID)
            if where is not None:
                stmt = stmt.where(where)
            changed = session.execute(stmt.values(**values)).rowcount
            session.commit()
            return changed

    def snapshot(self) -> RuntimeState:
        with self._session_factory() as session:
            row = session.get(ActuatorStateRow, ROW_ID)
            if row is None:
                return RuntimeState()
            return RuntimeState(
                siren_active=bool(row.siren_active),
                gates_locked=bool(row.gates_locked),
                alert_count=int(row.alert_count or 0),
                last_alert_time=float(row.last_alert_time or 0.0),
                last_alert_thread_id=row.last_alert_thread_id,
            )

    def actuators(self) -> ActuatorState:
        return self.snapshot().actuators

    def siren_activated(self, at: float) -> None:
        self._update_row(siren_active=True, alert_count=ActuatorStateRow.alert_count + 1, last_alert_time=at)

    def siren_deactivated(self) -> None:
        self._update_row(siren_active=False)

    def expire_siren(self, now: float, after_seconds: float) -> bool:
        where = ActuatorStateRow.siren_active.is_(True) & (ActuatorStateRow.last_alert_time < now - after_seconds)
        return self._update_row(where=where, siren_active=False) > 0

    def set_gates_locked(self, locked: bool) -> None:
        self._update_row(gates_locked=bool(locked))

    def set_last_alert_thread(self, thread_id: int) -> None:
        self._update_row(last_alert_thread_id=thread_id)

    def overwrite_runtime(self, **fields: Any) -> None:
        unknown = set(fields) - set(RUNTIME_FIELDS)
        if unknown:
            raise AttributeError(f"Unknown runtime state field(s): {sorted(unknown)}")
        if fields:
            self._update_row(**fields)

    # -- nodes --------------------------------------------------------------------------------
    def _mutate_node(self, node_id: str, change: Callable[[Optional[Dict[str, Any]]], Optional[Dict[str, Any]]]) -> bool:
        """Applies ``change`` to the node's data under a row lock; ``None`` from it means no write."""
        for attempt in (1, 2):
            with self._session_factory() as session:
                row = session.get(NodeStatus, node_id, with_for_update=True)
                data = change(dict(row.data) if row is not None else None)
                if data is None:
                    session.rollback()
                    return False
                if row is None:
                    session.add(NodeStatus(node_id=node_id, data=data, last_seen=_last_seen(data)))
                else:
                    row.data = data
                    row.last_seen = _last_seen(data)
                try:
                    session.commit()
                    return True
                except IntegrityError:
                    session.rollback()  # created concurrently: retry as an update
                    if attempt == 2:
                        raise
        return False

    def record_node_activity(self, node_id: str, ip: Optional[str] = None) -> None:
        now = self._clock()

        def change(data):
            if data is None:
                return new_node(node_id, ip, now)
            data["last_seen"] = now
            if ip:
                data["ip"] = ip
            return data

        self._mutate_node(node_id, change)

    def put_node(self, node_id: str, data: Dict[str, Any]) -> None:
        self._mutate_node(node_id, lambda _old: dict(data))

    def merge_node(self, node_id: str, fields: Dict[str, Any], *, create: bool = False) -> bool:
        def change(data):
            if data is None:
                if not create:
                    return None
                data = {}
            data.update(fields)
            return data

        return self._mutate_node(node_id, change)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._session_factory() as session:
            row = session.get(NodeStatus, node_id)
            return dict(row.data) if row is not None else None

    def list_nodes(self) -> Dict[str, Dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.execute(select(NodeStatus).order_by(NodeStatus.node_id)).scalars().all()
            return {row.node_id: dict(row.data) for row in rows}

    def remove_node(self, node_id: str) -> None:
        with self._session_factory() as session:
            session.execute(delete(NodeStatus).where(NodeStatus.node_id == node_id))
            session.commit()

    def clear_nodes(self) -> None:
        with self._session_factory() as session:
            session.execute(delete(NodeStatus))
            session.commit()

    def prune_nodes(self, older_than: float, keep: Iterable[str]) -> List[str]:
        keep = list(keep)
        stale = (NodeStatus.last_seen.is_(None) | (NodeStatus.last_seen < older_than))
        if keep:
            stale = stale & NodeStatus.node_id.not_in(keep)
        with self._session_factory() as session:
            ids = list(session.execute(select(NodeStatus.node_id).where(stale)).scalars())
            if ids:
                session.execute(delete(NodeStatus).where(NodeStatus.node_id.in_(ids)))
                session.commit()
            return ids

    # -- operational log ----------------------------------------------------------------------
    def add_log(self, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE") -> None:
        now = datetime.datetime.now()
        with self._session_factory() as session:
            session.execute(delete(OperationalLog).where(OperationalLog.expires_at <= now))
            session.add(OperationalLog(
                created_at=now, expires_at=now + datetime.timedelta(hours=LOG_TTL_HOURS),
                message=msg, level=level, camera_module=camera_module,
            ))
            session.flush()
            newest = select(OperationalLog.id).order_by(OperationalLog.id.desc()).limit(LOG_CAPACITY)
            session.execute(delete(OperationalLog).where(OperationalLog.id.not_in(newest.scalar_subquery())))
            session.commit()

    def list_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        stmt = (
            select(OperationalLog)
            .where(OperationalLog.expires_at > datetime.datetime.now())
            .order_by(OperationalLog.id.desc())
            .limit(min(limit, LOG_CAPACITY) if limit is not None else LOG_CAPACITY)
        )
        with self._session_factory() as session:
            return [_log_dict(row) for row in session.execute(stmt).scalars()]

    def purge_expired_logs(self) -> None:
        with self._session_factory() as session:
            session.execute(delete(OperationalLog).where(OperationalLog.expires_at <= datetime.datetime.now()))
            session.commit()
