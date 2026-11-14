"""Value objects for actuator state."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ActuatorState:
    siren_active: bool
    gates_locked: bool
