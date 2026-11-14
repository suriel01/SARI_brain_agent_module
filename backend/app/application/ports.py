"""Ports the use cases depend on; `app.adapters` provides the concrete implementations."""
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple

from ..domain.actors import Actor
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

    # Operational log (newest first, 24 h TTL, capped)
    def add_log(self, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE") -> None: ...

    def list_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]: ...

    def purge_expired_logs(self) -> None: ...


# Former name of the port, kept so existing imports keep working.
StatePort = StateRepository
