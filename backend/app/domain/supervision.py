"""Heartbeat supervision: a device that stops reporting is a fault, never an alarm (no siren)."""
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class Heartbeat:
    device_id: str
    kind: str
    last_seen: Optional[float]
    timeout: float

    def overdue(self, now: float) -> bool:
        return self.last_seen is None or now - self.last_seen > self.timeout


@dataclass(frozen=True)
class Fault:
    device_id: str
    kind: str
    reason: str


def _fault(hb: Heartbeat, now: float) -> Fault:
    reason = ("never reported a heartbeat" if hb.last_seen is None
              else f"no heartbeat for {round(now - hb.last_seen)}s (timeout {round(hb.timeout)}s)")
    return Fault(device_id=hb.device_id, kind=hb.kind, reason=reason)


def evaluate_supervision(heartbeats: Iterable[Heartbeat], active: Set[str],
                         now: float) -> Tuple[List[Fault], List[str]]:
    """Returns (faults to raise, device ids to clear). Faults of devices no longer supervised clear too."""
    beats: Dict[str, Heartbeat] = {hb.device_id: hb for hb in heartbeats}
    to_raise = [_fault(hb, now) for hb in beats.values() if hb.overdue(now) and hb.device_id not in active]
    to_clear = sorted(d for d in active if d not in beats or not beats[d].overdue(now))
    return to_raise, to_clear
