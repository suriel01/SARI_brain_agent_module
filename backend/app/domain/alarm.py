"""Alarm state machine, modelled on Home Assistant Alarmo.

    disarmed ─arm─► arming (exit delay) ─► armed_{away,home,night} ─entry zone─► pending (entry delay) ─► triggered
                                                  └──────────── immediate zone ──────────────────────────────┘
    triggered lasts ``trigger_time`` and returns to its armed mode (or to disarmed when tamper raised it there).
    disarm is valid from every state. "Failed to arm" is an event recorded by the application, never a state.

Pure functions over immutable values: the caller supplies ``now`` and persists the result.
"""
from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict, FrozenSet, Optional, Tuple

from .policy import SIREN_CONFIDENCE_THRESHOLD, should_raise_alarm

TAMPER_EVENT = "tamper"


class InvalidTransition(ValueError):
    """The requested change is not allowed from the current state (or names an unknown mode)."""


class AlarmState(str, Enum):
    DISARMED = "disarmed"
    ARMING = "arming"
    ARMED_AWAY = "armed_away"
    ARMED_HOME = "armed_home"
    ARMED_NIGHT = "armed_night"
    PENDING = "pending"
    TRIGGERED = "triggered"


class ArmMode(str, Enum):
    AWAY = "away"
    HOME = "home"
    NIGHT = "night"

    @classmethod
    def parse(cls, value: str) -> "ArmMode":
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            raise InvalidTransition(f"unknown arm mode: {value!r}") from None


ARMED_STATES = {
    ArmMode.AWAY: AlarmState.ARMED_AWAY,
    ArmMode.HOME: AlarmState.ARMED_HOME,
    ArmMode.NIGHT: AlarmState.ARMED_NIGHT,
}


@dataclass(frozen=True)
class ModeConfig:
    exit_delay: float
    entry_delay: float


@dataclass(frozen=True)
class ZoneConfig:
    """Modes that arm this zone; an immediate zone triggers at once, an entry zone starts the entry delay."""

    modes: FrozenSet[ArmMode]
    immediate: bool = True


@dataclass(frozen=True)
class AlarmConfig:
    modes: Dict[ArmMode, ModeConfig]
    zones: Dict[str, ZoneConfig]
    trigger_time: float
    default_zone: str = "perimeter"
    threshold: float = SIREN_CONFIDENCE_THRESHOLD

    def zone(self, zone_id: Optional[str]) -> ZoneConfig:
        return self.zones.get(zone_id or self.default_zone) or self.zones[self.default_zone]


# Camera detections today carry no zone, so they all land in the immediate "perimeter" zone.
DEFAULT_CONFIG = AlarmConfig(
    modes={
        ArmMode.AWAY: ModeConfig(exit_delay=60, entry_delay=30),
        ArmMode.HOME: ModeConfig(exit_delay=0, entry_delay=30),
        ArmMode.NIGHT: ModeConfig(exit_delay=0, entry_delay=30),
    },
    zones={"perimeter": ZoneConfig(modes=frozenset(ArmMode), immediate=True)},
    trigger_time=30,
)


@dataclass(frozen=True)
class AlarmStatus:
    state: AlarmState
    mode: Optional[ArmMode]  # target or armed mode; None when disarmed (or triggered from disarmed)
    since: float
    deadline: Optional[float] = None  # end of the exit delay, entry delay or trigger time
    cause: str = ""  # what started pending/triggered (a node id, "tamper:<node>")

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "mode": self.mode.value if self.mode else None,
            "since": self.since,
            "deadline": self.deadline,
            "cause": self.cause,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AlarmStatus":
        mode = data.get("mode")
        return cls(
            state=AlarmState(data["state"]),
            mode=ArmMode(mode) if mode else None,
            since=float(data["since"]),
            deadline=None if data.get("deadline") is None else float(data["deadline"]),
            cause=data.get("cause") or "",
        )


# Fail toward safety: before anyone chooses a mode the system behaves as it always did (armed).
INITIAL_STATUS = AlarmStatus(state=AlarmState.ARMED_AWAY, mode=ArmMode.AWAY, since=0.0)


@dataclass(frozen=True)
class Detection:
    event_type: str
    confidence: float
    zone: Optional[str] = None
    source: str = ""


class Outcome(str, Enum):
    RECORD_ONLY = "record_only"
    ENTRY_DELAY = "entry_delay"
    RAISE = "raise"


def _armed(mode: ArmMode, now: float) -> AlarmStatus:
    return AlarmStatus(state=ARMED_STATES[mode], mode=mode, since=now)


def _disarmed(now: float) -> AlarmStatus:
    return AlarmStatus(state=AlarmState.DISARMED, mode=None, since=now)


def arm(status: AlarmStatus, mode: ArmMode, now: float, config: AlarmConfig) -> AlarmStatus:
    """Arms from disarmed or arming (exit delay), or switches armed modes at once; pending and triggered
    must be disarmed first."""
    if status.state in (AlarmState.PENDING, AlarmState.TRIGGERED):
        raise InvalidTransition(f"cannot arm while {status.state.value}; disarm first")
    if status.state in ARMED_STATES.values():
        # Already protected: never open an unprotected exit-delay window.
        return status if status.mode is mode else _armed(mode, now)
    exit_delay = config.modes[mode].exit_delay
    if exit_delay > 0:
        return AlarmStatus(state=AlarmState.ARMING, mode=mode, since=now, deadline=now + exit_delay)
    return _armed(mode, now)


def disarm(status: AlarmStatus, now: float) -> AlarmStatus:
    return _disarmed(now)


def advance(status: AlarmStatus, now: float, config: AlarmConfig) -> AlarmStatus:
    """Applies an elapsed timer: exit delay → armed, entry delay → triggered, trigger time → back."""
    if status.deadline is None or now < status.deadline:
        return status
    if status.state is AlarmState.ARMING:
        return _armed(status.mode, now)
    if status.state is AlarmState.PENDING:
        return AlarmStatus(state=AlarmState.TRIGGERED, mode=status.mode, since=now,
                           deadline=now + config.trigger_time, cause=status.cause)
    if status.state is AlarmState.TRIGGERED:
        return _armed(status.mode, now) if status.mode else _disarmed(now)
    return status


def _trigger(status: AlarmStatus, now: float, config: AlarmConfig, cause: str) -> AlarmStatus:
    if status.state is AlarmState.TRIGGERED:  # sounding again extends the trigger time, keeps its start
        return replace(status, deadline=now + config.trigger_time)
    return AlarmStatus(state=AlarmState.TRIGGERED, mode=status.mode, since=now,
                       deadline=now + config.trigger_time, cause=cause)


def evaluate(status: AlarmStatus, detection: Detection, now: float,
             config: AlarmConfig) -> Tuple[Outcome, AlarmStatus]:
    """Decides what a detection does in the current state. Only RAISE sounds the siren."""
    if detection.event_type == TAMPER_EVENT:
        return Outcome.RAISE, _trigger(status, now, config, f"tamper:{detection.source}")
    if not should_raise_alarm(detection.event_type, detection.confidence, config.threshold):
        return Outcome.RECORD_ONLY, status
    if status.state in (AlarmState.DISARMED, AlarmState.ARMING) or status.mode is None:
        return Outcome.RECORD_ONLY, status
    zone = config.zone(detection.zone)
    if status.mode not in zone.modes:
        return Outcome.RECORD_ONLY, status
    if status.state is AlarmState.TRIGGERED:
        return Outcome.RAISE, _trigger(status, now, config, detection.source)
    entry_delay = config.modes[status.mode].entry_delay
    if zone.immediate or entry_delay <= 0:
        return Outcome.RAISE, _trigger(status, now, config, detection.source)
    if status.state is AlarmState.PENDING:
        return Outcome.RECORD_ONLY, status
    return Outcome.ENTRY_DELAY, AlarmStatus(state=AlarmState.PENDING, mode=status.mode, since=now,
                                            deadline=now + entry_delay, cause=detection.source)


__all__ = [
    "ARMED_STATES", "DEFAULT_CONFIG", "INITIAL_STATUS", "TAMPER_EVENT", "AlarmConfig", "AlarmState", "AlarmStatus",
    "ArmMode", "Detection", "InvalidTransition", "ModeConfig", "Outcome", "ZoneConfig", "advance", "arm", "disarm",
    "evaluate",
]
