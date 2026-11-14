"""AlarmRepository over `alarm_state`, `alarm_event` and `alarm_fault`.

Every status change locks the single status row (``SELECT ... FOR UPDATE`` on PostgreSQL), so the API
(arm/disarm) and the worker (alerts, timers) never overwrite each other's transition.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...domain.alarm import INITIAL_STATUS, AlarmState, AlarmStatus, ArmMode
from ...models.models import AlarmEventRow, AlarmFaultRow, AlarmStateRow

ROW_ID = 1
TIMELINE_MAX = 500


def _status(row: AlarmStateRow) -> AlarmStatus:
    return AlarmStatus(state=AlarmState(row.state), mode=ArmMode(row.mode) if row.mode else None,
                       since=row.since, deadline=row.deadline, cause=row.cause or "")


def _write(row: AlarmStateRow, status: AlarmStatus) -> None:
    row.state = status.state.value
    row.mode = status.mode.value if status.mode else None
    row.since = status.since
    row.deadline = status.deadline
    row.cause = status.cause[:200]


def _event_dict(row: AlarmEventRow) -> Dict[str, Any]:
    return {"id": row.id, "at": row.at, "kind": row.kind, "from_state": row.from_state, "to_state": row.to_state,
            "cause": row.cause, "actor": row.actor}


class SqlAlarmRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def _row(self, session: Session, *, lock: bool) -> AlarmStateRow:
        row = session.get(AlarmStateRow, ROW_ID, with_for_update=lock)
        if row is None:
            try:
                with session.begin_nested():
                    fresh = AlarmStateRow(id=ROW_ID)
                    _write(fresh, INITIAL_STATUS)
                    session.add(fresh)
            except IntegrityError:
                pass  # another process created it first
            row = session.get(AlarmStateRow, ROW_ID, with_for_update=lock, populate_existing=True)
        return row

    def read(self) -> AlarmStatus:
        with self._session_factory() as session:
            status = _status(self._row(session, lock=False))
            session.commit()
            return status

    def update(self, change: Callable[[AlarmStatus], AlarmStatus], *, actor: str = "",
               kind: str = "transition") -> Tuple[AlarmStatus, AlarmStatus]:
        with self._session_factory() as session:
            row = self._row(session, lock=True)
            before = _status(row)
            after = change(before)
            if after != before:
                _write(row, after)
                if after.state is not before.state:
                    session.add(AlarmEventRow(at=after.since, kind=kind, from_state=before.state.value,
                                              to_state=after.state.value, cause=after.cause[:200], actor=actor[:100]))
            session.commit()
            return before, after

    def record_event(self, kind: str, *, at: float, actor: str = "", cause: str = "",
                     state: Optional[str] = None) -> None:
        with self._session_factory() as session:
            session.add(AlarmEventRow(at=at, kind=kind, from_state=state, to_state=state, cause=cause[:200],
                                      actor=actor[:100]))
            session.commit()

    def timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), TIMELINE_MAX))
        with self._session_factory() as session:
            rows = session.query(AlarmEventRow).order_by(AlarmEventRow.id.desc()).limit(limit).all()
            return [_event_dict(r) for r in rows]

    def raise_fault(self, device_id: str, kind: str, reason: str, at: float) -> bool:
        with self._session_factory() as session:
            try:
                with session.begin_nested():
                    session.add(AlarmFaultRow(device_id=device_id[:100], kind=kind[:30], since=at, reason=reason[:200]))
            except IntegrityError:
                session.rollback()
                return False
            session.add(AlarmEventRow(at=at, kind="fault", cause=f"{device_id}: {reason}"[:200], actor="system:supervision"))
            session.commit()
            return True

    def clear_fault(self, device_id: str, at: float) -> bool:
        with self._session_factory() as session:
            removed = session.execute(delete(AlarmFaultRow).where(AlarmFaultRow.device_id == device_id)).rowcount
            if removed:
                session.add(AlarmEventRow(at=at, kind="fault_cleared", cause=device_id[:200], actor="system:supervision"))
            session.commit()
            return bool(removed)

    def active_faults(self) -> List[Dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.query(AlarmFaultRow).order_by(AlarmFaultRow.since).all()
            return [{"device_id": r.device_id, "kind": r.kind, "since": r.since, "reason": r.reason} for r in rows]
