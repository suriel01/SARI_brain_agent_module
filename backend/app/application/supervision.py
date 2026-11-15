"""Device supervision run by the worker: vision node heartbeats and the siren service health.

A missed heartbeat stores a fault (timeline, dashboard, Telegram) and never sounds the siren. Node loss
is already announced on Telegram by the watchdog's sabotage alert, so only other devices notify here.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

from ..domain.supervision import Heartbeat, evaluate_supervision
from .ports import AlarmRepository, BroadcastPort

logger = logging.getLogger("sari_supervision")

NODE_TIMEOUT_SECONDS = 15.0
SIREN_TIMEOUT_SECONDS = 15.0
SIREN_PROBE_INTERVAL_SECONDS = 10.0
SIREN_DEVICE = "siren:service"

FAULT_MSG = ("⚠️ *FALLA DE SUPERVISIÓN*\n\n• *Dispositivo:* `{device}`\n• *Motivo:* {reason}\n\n"
             "La sirena no se activa por una falla; revise el equipo.")
CLEARED_MSG = "✅ *Supervisión restablecida:* `{device}` vuelve a reportar."


@dataclass
class SupervisionResult:
    raised: List[str] = field(default_factory=list)
    cleared: List[str] = field(default_factory=list)


class Supervisor:
    def __init__(self, *, repo: AlarmRepository, broadcast: BroadcastPort, notify: Callable[[str], object],
                 siren_health: Callable[[], bool], clock: Callable[[], float] = time.time):
        self.repo = repo
        self.broadcast = broadcast
        self.notify = notify
        self.siren_health = siren_health
        self.clock = clock
        self._siren_last_ok: Optional[float] = None  # process-local: only the worker supervises
        self._last_probe: Optional[float] = None

    def _probe_siren(self, now: float) -> None:
        if self._siren_last_ok is None:
            self._siren_last_ok = now  # grace period from the first pass
        if self._last_probe is not None and now - self._last_probe < SIREN_PROBE_INTERVAL_SECONDS:
            return
        self._last_probe = now
        try:
            ok = bool(self.siren_health())
        except Exception as exc:  # noqa: BLE001 - an unreachable siren is a fault, not a crash
            logger.warning("Siren health probe failed: %s", exc)
            ok = False
        if ok:
            self._siren_last_ok = now

    def heartbeats(self, node_ids: Iterable[str], nodes: Dict[str, dict]) -> List[Heartbeat]:
        beats = [Heartbeat(f"node:{nid}", "node", (nodes.get(nid) or {}).get("last_seen"), NODE_TIMEOUT_SECONDS)
                 for nid in sorted(node_ids)]
        beats.append(Heartbeat(SIREN_DEVICE, "siren", self._siren_last_ok, SIREN_TIMEOUT_SECONDS))
        return beats

    def run(self, node_ids: Iterable[str], nodes: Dict[str, dict], now: Optional[float] = None) -> SupervisionResult:
        now = self.clock() if now is None else now
        self._probe_siren(now)
        active = {f["device_id"] for f in self.repo.active_faults()}
        to_raise, to_clear = evaluate_supervision(self.heartbeats(node_ids, nodes), active, now)
        result = SupervisionResult()
        for fault in to_raise:
            if not self.repo.raise_fault(fault.device_id, fault.kind, fault.reason, now):
                continue  # another pass raised it first
            result.raised.append(fault.device_id)
            logger.warning("[SUPERVISION] Fault on %s: %s", fault.device_id, fault.reason)
            self._publish({"event": "alarm_fault", "active": True, "fault": {
                "device_id": fault.device_id, "kind": fault.kind, "since": now, "reason": fault.reason}})
            if fault.kind != "node":
                self._notify(FAULT_MSG.format(device=fault.device_id, reason=fault.reason))
        for device_id in to_clear:
            if not self.repo.clear_fault(device_id, now):
                continue
            result.cleared.append(device_id)
            logger.info("[SUPERVISION] Fault cleared on %s", device_id)
            self._publish({"event": "alarm_fault", "device_id": device_id, "active": False})
            if not device_id.startswith("node:"):
                self._notify(CLEARED_MSG.format(device=device_id))
        return result

    def _publish(self, payload: dict) -> None:
        try:
            self.broadcast.publish(payload)
        except Exception:  # noqa: BLE001 - best effort
            logger.warning("Could not broadcast a supervision event")

    def _notify(self, text: str) -> None:
        try:
            self.notify(text)
        except Exception:  # noqa: BLE001 - Telegram is best effort
            logger.warning("Could not send a supervision notification")
