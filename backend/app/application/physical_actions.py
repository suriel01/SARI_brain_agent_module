"""ExecutePhysicalAction: the single choke point every channel uses to drive physical hardware."""
import logging
import time
from typing import Callable, Optional

from ..domain.actions import ACTIVATE_SIREN, DEACTIVATE_SIREN, LOCK_GATES, UNLOCK_GATES, siren_duration
from ..domain.actors import Actor
from .ports import AuditPort, BroadcastPort, SirenPort, StatePort

AUDITED_RESULTS = ("success", "denied", "failed")

logger = logging.getLogger("sari_physical_actions")


class ExecutePhysicalAction:
    """Permission check, actuator, state update, broadcast on confirmed success, then one audit row."""

    def __init__(self, *, siren: SirenPort, audit: AuditPort, broadcast: BroadcastPort, state: StatePort,
                 clock: Callable[[], float] = time.time):
        self.siren = siren
        self.audit = audit
        self.broadcast = broadcast
        self.state = state
        self.clock = clock

    def __call__(self, tool_name: str, args: Optional[dict] = None, *, actor: Optional[Actor]) -> dict:
        call = {"state_ok": True}  # per call: the use case instance is shared across threads
        result = self._run(tool_name, args or {}, actor, call)
        if not call["state_ok"] and result.get("status") in ("success", "denied"):
            result["state_persisted"] = False
        status = result.get("status")
        self.audit.record(actor, tool_name, status if status in AUDITED_RESULTS else "failed", result.get("message", ""))
        return result

    def _persist(self, call: dict, method: str, *args, **kwargs) -> None:
        """State writes never undo a hardware action that already happened: fail open and flag it."""
        try:
            getattr(self.state, method)(*args, **kwargs)
        except Exception:  # noqa: BLE001 - any store failure must not hide that the hardware acted
            call["state_ok"] = False
            logger.exception("State store write %s failed; the physical action result stands", method)

    def _run(self, tool_name: str, args: dict, actor: Optional[Actor], call: dict) -> dict:
        if actor is None or not actor.may_run(tool_name):
            who = actor.name if actor else "anonymous"
            via = actor.channel if actor else "unknown"
            self._persist(call, "add_log", f"⛔ Physical action '{tool_name}' denied for [{who}] via {via}", level="WARN", camera_module="HARDWARE_CTRL")
            return {"status": "denied", "message": "⛔ Permission denied: hardware control not authorized."}

        if tool_name in ACTIVATE_SIREN:
            duration = siren_duration(args)
            ok, reason = self.siren.activate(duration)
            if not ok:
                self._persist(call, "add_log", f"❌ Siren activation FAILED: {reason}", level="ERROR", camera_module="HARDWARE_CTRL")
                return {"status": "failed", "message": f"❌ Siren activation failed: {reason}."}
            self._persist(call, "siren_activated", self.clock())
            self._persist(call, "add_log", f"🚨 Physical Siren activated for {duration}s", level="ERROR", camera_module="HARDWARE_CTRL")
            self.broadcast.publish({"event": "siren_activated"})
            return {"status": "success", "message": "🚨 Siren activated."}

        if tool_name in DEACTIVATE_SIREN:
            ok, reason = self.siren.deactivate()
            if not ok:
                self._persist(call, "add_log", f"❌ Siren deactivation FAILED: {reason}", level="ERROR", camera_module="HARDWARE_CTRL")
                return {"status": "failed", "message": f"❌ Siren deactivation failed: {reason}. The siren may still be sounding."}
            self._persist(call, "siren_deactivated")
            self._persist(call, "add_log", "🔊 Siren deactivated / silenced by operator", level="INFO", camera_module="HARDWARE_CTRL")
            self.broadcast.publish({"event": "siren_deactivated"})
            return {"status": "success", "message": "🔊 Siren turned off & silenced."}

        if tool_name in LOCK_GATES:
            self._persist(call, "set_gates_locked", True)
            self._persist(call, "add_log", "🔒 Perimeter gates locked (simulated: no gate hardware connected)", level="WARN", camera_module="HARDWARE_CTRL")
            return {"status": "success", "simulated": True, "message": "🔒 Perimeter gates locked (simulated: no gate hardware connected)."}

        if tool_name in UNLOCK_GATES:
            self._persist(call, "set_gates_locked", False)
            self._persist(call, "add_log", "🔓 Perimeter gates unlocked (simulated: no gate hardware connected)", level="INFO", camera_module="HARDWARE_CTRL")
            return {"status": "success", "simulated": True, "message": "🔓 Perimeter gates unlocked (simulated: no gate hardware connected)."}

        return {"status": "error", "message": f"Unknown hardware tool: {tool_name}"}
