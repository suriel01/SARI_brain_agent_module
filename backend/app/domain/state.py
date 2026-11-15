"""Value objects and constants for the live SOC state."""
from dataclasses import dataclass
from typing import Optional

# Node fields only a node can report; until it does they stay None (unknown, never invented).
NODE_TELEMETRY_FIELDS = (
    "ram_used_gb", "ram_total_gb", "cpu_load_pct", "gpu_load_pct", "temp_c", "fps", "link_status",
)

LOG_TTL_HOURS = 24
LOG_CAPACITY = 300
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Runtime fields a compatibility caller may overwrite directly (tests, legacy facade).
RUNTIME_FIELDS = ("siren_active", "gates_locked", "alert_count", "last_alert_time", "last_alert_thread_id")


@dataclass(frozen=True)
class ActuatorState:
    siren_active: bool
    gates_locked: bool


@dataclass(frozen=True)
class RuntimeState:
    """Actuators plus alert counters, as one consistent read."""

    siren_active: bool = False
    gates_locked: bool = False
    alert_count: int = 0
    last_alert_time: float = 0.0
    last_alert_thread_id: Optional[int] = None

    @property
    def actuators(self) -> ActuatorState:
        return ActuatorState(siren_active=self.siren_active, gates_locked=self.gates_locked)


def new_node(node_id: str, ip: Optional[str], now: float) -> dict:
    """A node first seen through activity (an alert): telemetry it has not reported is None."""
    return {
        "node_id": node_id,
        "name": f"Jetson Node ({node_id})",
        "ip": ip,
        **{field: None for field in NODE_TELEMETRY_FIELDS},
        "last_seen": now,
    }
