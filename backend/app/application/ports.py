"""Ports the use cases depend on; `app.adapters` provides the concrete implementations."""
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple

from ..domain.actors import Actor
from ..domain.alarm import AlarmStatus
from ..domain.state import ActuatorState, RuntimeState


class SirenPort(Protocol):
    """The physical siren. Each call returns (ok, reason); ok only when the hardware confirmed it."""

    def activate(self, duration: Any) -> Tuple[bool, str]: ...

    def deactivate(self) -> Tuple[bool, str]: ...


class AuditPort(Protocol):
    """Persistent physical-action audit trail. Must never raise."""

    def record(self, actor: Optional[Actor], tool_name: str, result: str, detail: str = "") -> None: ...


class BroadcastPort(Protocol):
    """Best-effort realtime notification of the dashboard."""

    def publish(self, payload: dict, background_tasks=None, *, warn: bool = False) -> None: ...


class StateRepository(Protocol):
    """Live SOC state shared by every process: actuators, alert counters, vision nodes and the operational log.

    Every write is atomic on its own (no read-modify-write window between callers): counters are
    incremented in the store, node merges lock the node's row, and the siren auto-off is a conditional update.
    """

    # Actuators and alert counters
    def snapshot(self) -> RuntimeState: ...

    def actuators(self) -> ActuatorState: ...

    def siren_activated(self, at: float) -> None:
        """siren_active = True, alert_count += 1, last_alert_time = at, in one atomic write."""

    def siren_deactivated(self) -> None: ...

    def expire_siren(self, now: float, after_seconds: float) -> bool:
        """Turns the siren flag off when it has been on longer than ``after_seconds``. True when it changed."""

    def set_gates_locked(self, locked: bool) -> None: ...

    def set_last_alert_thread(self, thread_id: int) -> None: ...

    def overwrite_runtime(self, **fields: Any) -> None:
        """Sets runtime fields verbatim (compatibility facade and tests only); see `RUNTIME_FIELDS`."""

    # Vision nodes (last_seen is a Unix timestamp inside the node's data)
    def record_node_activity(self, node_id: str, ip: Optional[str] = None) -> None: ...

    def put_node(self, node_id: str, data: Dict[str, Any]) -> None:
        """Replaces the node's data."""

    def merge_node(self, node_id: str, fields: Dict[str, Any], *, create: bool = False) -> bool:
        """Merges fields into an existing node (or a new empty one when ``create``). True when stored."""

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]: ...

    def list_nodes(self) -> Dict[str, Dict[str, Any]]: ...

    def remove_node(self, node_id: str) -> None: ...

    def clear_nodes(self) -> None: ...

    def prune_nodes(self, older_than: float, keep: Iterable[str]) -> List[str]:
        """Removes nodes not in ``keep`` whose last_seen is missing or older than ``older_than``."""

    # Per-node flags that telemetry must not overwrite
    def mark_disconnect_notified(self, node_id: str) -> bool:
        """Atomic test-and-set of the watchdog debounce. True only for the caller that set it."""

    def clear_disconnect_notified(self, node_id: str) -> bool:
        """Re-arms the disconnection alert. True when it was set."""

    def set_tracking_enabled(self, node_id: str, enabled: bool) -> None: ...

    def tracking_overrides(self) -> Dict[str, bool]:
        """Operator tracking choices by node id (nodes without a choice are absent)."""

    # Operational log (newest first, 24 h TTL, capped)
    def add_log(self, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE") -> None: ...

    def list_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]: ...

    def purge_expired_logs(self) -> None: ...


class AlarmRepository(Protocol):
    """Alarm status (one row shared by every process), its timeline and the active supervision faults."""

    def read(self) -> AlarmStatus: ...

    def update(self, change: Callable[[AlarmStatus], AlarmStatus], *, actor: str = "",
               kind: str = "transition") -> Tuple[AlarmStatus, AlarmStatus]:
        """Locks the status, applies ``change``, stores the result and appends a timeline event when the
        state changed, in one transaction. Returns (before, after). If ``change`` raises, nothing is written."""

    def record_event(self, kind: str, *, at: float, actor: str = "", cause: str = "",
                     state: Optional[str] = None) -> None: ...

    def timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Newest first."""

    def raise_fault(self, device_id: str, kind: str, reason: str, at: float) -> bool:
        """Stores an active fault and its timeline event. True only when it was not already active."""

    def clear_fault(self, device_id: str, at: float) -> bool:
        """Removes an active fault and records it as cleared. True only when it was active."""

    def active_faults(self) -> List[Dict[str, Any]]: ...


# Former name of the port, kept so existing imports keep working.
StatePort = StateRepository
