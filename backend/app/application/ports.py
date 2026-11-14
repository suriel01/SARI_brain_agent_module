"""Ports the use cases depend on; `app.adapters` provides the concrete implementations."""
from typing import Any, Optional, Protocol, Tuple

from ..domain.actors import Actor
from ..domain.state import ActuatorState


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


class StatePort(Protocol):
    """Live SOC state: actuators, alert counters, node activity and the operational log."""

    def actuators(self) -> ActuatorState: ...

    def siren_activated(self, at: float) -> None: ...

    def siren_deactivated(self) -> None: ...

    def set_gates_locked(self, locked: bool) -> None: ...

    def add_log(self, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE") -> None: ...

    def set_last_alert_thread(self, thread_id: int) -> None: ...

    def record_node_activity(self, node_id: str, ip: Optional[str] = None) -> None: ...
