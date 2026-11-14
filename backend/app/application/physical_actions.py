"""ExecutePhysicalAction: the single choke point every channel uses to drive physical hardware."""
import time
from typing import Callable, Optional

from ..domain.actions import ACTIVATE_SIREN, DEACTIVATE_SIREN, LOCK_GATES, UNLOCK_GATES, siren_duration
from ..domain.actors import Actor
from .ports import AuditPort, BroadcastPort, SirenPort, StatePort

AUDITED_RESULTS = ("success", "denied", "failed")


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
        result = self._run(tool_name, args or {}, actor)
        status = result.get("status")
        self.audit.record(actor, tool_name, status if status in AUDITED_RESULTS else "failed", result.get("message", ""))
        return result

    def _run(self, tool_name: str, args: dict, actor: Optional[Actor]) -> dict:
        if actor is None or not actor.may_run(tool_name):
            who = actor.name if actor else "anonymous"
            via = actor.channel if actor else "unknown"
            self.state.add_log(f"⛔ Physical action '{tool_name}' denied for [{who}] via {via}", level="WARN", camera_module="HARDWARE_CTRL")
            return {"status": "denied", "message": "⛔ Permission denied: hardware control not authorized."}

        if tool_name in ACTIVATE_SIREN:
            duration = siren_duration(args)
            ok, reason = self.siren.activate(duration)
            if not ok:
                self.state.add_log(f"❌ Siren activation FAILED: {reason}", level="ERROR", camera_module="HARDWARE_CTRL")
                return {"status": "failed", "message": f"❌ Siren activation failed: {reason}."}
            self.state.siren_activated(self.clock())
            self.state.add_log(f"🚨 Physical Siren activated for {duration}s", level="ERROR", camera_module="HARDWARE_CTRL")
            self.broadcast.publish({"event": "siren_activated"})
            return {"status": "success", "message": "🚨 Siren activated."}

        if tool_name in DEACTIVATE_SIREN:
            ok, reason = self.siren.deactivate()
            if not ok:
                self.state.add_log(f"❌ Siren deactivation FAILED: {reason}", level="ERROR", camera_module="HARDWARE_CTRL")
                return {"status": "failed", "message": f"❌ Siren deactivation failed: {reason}. The siren may still be sounding."}
            self.state.siren_deactivated()
            self.state.add_log("🔊 Siren deactivated / silenced by operator", level="INFO", camera_module="HARDWARE_CTRL")
            self.broadcast.publish({"event": "siren_deactivated"})
            return {"status": "success", "message": "🔊 Siren turned off & silenced."}

        if tool_name in LOCK_GATES:
            self.state.set_gates_locked(True)
            self.state.add_log("🔒 Perimeter gates locked (simulated: no gate hardware connected)", level="WARN", camera_module="HARDWARE_CTRL")
            return {"status": "success", "simulated": True, "message": "🔒 Perimeter gates locked (simulated: no gate hardware connected)."}

        if tool_name in UNLOCK_GATES:
            self.state.set_gates_locked(False)
            self.state.add_log("🔓 Perimeter gates unlocked (simulated: no gate hardware connected)", level="INFO", camera_module="HARDWARE_CTRL")
            return {"status": "success", "simulated": True, "message": "🔓 Perimeter gates unlocked (simulated: no gate hardware connected)."}

        return {"status": "error", "message": f"Unknown hardware tool: {tool_name}"}
