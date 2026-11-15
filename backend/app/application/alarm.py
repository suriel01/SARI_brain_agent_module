"""Alarm use cases: arm, disarm, apply a detection, advance timers.

Arming and disarming are human decisions: only an actor with hardware permission on a human channel
may change the mode, and every attempt is audited in `physical_action_log`. The siren itself is
always driven through the physical-action choke point (`ExecutePhysicalAction`).
"""
import logging
import math
import time
from typing import Callable, Optional

from ..domain.actions import DEFAULT_SIREN_SECONDS
from ..domain.actors import Actor
from ..domain.alarm import (
    DEFAULT_CONFIG,
    AlarmConfig,
    AlarmState,
    AlarmStatus,
    ArmMode,
    Detection,
    InvalidTransition,
    Outcome,
    advance,
    arm,
    disarm,
    evaluate,
)
from ..domain.policy import should_raise_alarm
from .ports import AlarmRepository, AuditPort, BroadcastPort

logger = logging.getLogger("sari_alarm")

SYSTEM_ACTOR = Actor.system("alarm")
DISARM_SILENCES = (AlarmState.PENDING, AlarmState.TRIGGERED)
IGNORED_EVENT_INTERVAL_SECONDS = 60.0  # one "detection_ignored" timeline row per node per minute


class AlarmService:
    def __init__(self, *, repo: AlarmRepository, physical_action: Callable[..., dict], audit: AuditPort,
                 broadcast: BroadcastPort, config: AlarmConfig = DEFAULT_CONFIG,
                 clock: Callable[[], float] = time.time):
        self.repo = repo
        self.physical_action = physical_action
        self.audit = audit
        self.broadcast = broadcast
        self.config = config
        self.clock = clock
        self._ignored_logged: dict = {}  # node -> last "detection_ignored" row (process-local)
        self._siren_owed = False  # an entry-delay siren that failed; retried while triggered (worker only)

    # -- reading ------------------------------------------------------------------------------
    def status(self) -> AlarmStatus:
        return self.repo.read()

    def describe(self, status: AlarmStatus, now: Optional[float] = None) -> dict:
        now = self.clock() if now is None else now
        remaining = None if status.deadline is None else max(0, math.ceil(status.deadline - now))
        return {**status.to_dict(), "remaining_seconds": remaining}

    def view(self) -> dict:
        return {**self.describe(self.repo.read()), "faults": self.repo.active_faults()}

    def timeline(self, limit: int = 50) -> list:
        return self.repo.timeline(limit)

    # -- human mode changes --------------------------------------------------------------------
    def arm(self, actor: Optional[Actor], mode_name: str, *, force: bool = False) -> dict:
        try:
            mode = ArmMode.parse(mode_name)
        except InvalidTransition as exc:
            return {"status": "invalid_mode", "message": str(exc)}
        tool = f"alarm_arm_{mode.value}"
        if actor is None or not actor.may_change_alarm_mode():
            self.audit.record(actor, tool, "denied", "alarm mode change not authorized")
            return {"status": "denied", "message": "⛔ Permission denied: alarm control not authorized."}
        now = self.clock()
        faults = self.repo.active_faults()
        if faults and not force:
            devices = ", ".join(f["device_id"] for f in faults)
            self._safe_event("failed_to_arm", at=now, actor=actor.name, cause=f"active faults: {devices}"[:200])
            self.audit.record(actor, tool, "failed", f"failed_to_arm: active faults ({devices})")
            return {"status": "failed_to_arm", "message": f"Active faults: {devices}. Fix them or force arming.",
                    "faults": faults}
        try:
            _, after = self.repo.update(lambda s: arm(s, mode, now, self.config), actor=actor.name)
        except InvalidTransition as exc:
            self.audit.record(actor, tool, "failed", str(exc))
            return {"status": "invalid_transition", "message": str(exc)}
        detail = "forced with active faults" if faults else ""
        self.audit.record(actor, tool, "success", detail)
        return {"status": "success", "alarm": self._announce(after, now)}

    def disarm(self, actor: Optional[Actor]) -> dict:
        if actor is None or not actor.may_change_alarm_mode():
            self.audit.record(actor, "alarm_disarm", "denied", "alarm mode change not authorized")
            return {"status": "denied", "message": "⛔ Permission denied: alarm control not authorized."}
        now = self.clock()
        before, after = self.repo.update(lambda s: disarm(s, now), actor=actor.name)
        self.audit.record(actor, "alarm_disarm", "success", f"from {before.state.value}")
        siren_result = None
        if before.state in DISARM_SILENCES:
            siren_result = self._drive("desactivar_sirena", {}, actor)
        return {"status": "success", "alarm": self._announce(after, now), "siren_result": siren_result}

    # -- detections and timers -----------------------------------------------------------------
    def on_detection(self, detection: Detection) -> Outcome:
        """Applies a detection to the alarm. Raises when the alarm store is unavailable: the caller then
        falls back to the confidence threshold so the siren still sounds."""
        now = self.clock()
        decided = {}

        def change(status: AlarmStatus) -> AlarmStatus:
            decided["outcome"], after = evaluate(status, detection, now, self.config)
            return after

        before, after = self.repo.update(change, actor=f"node:{detection.source}")
        outcome = decided["outcome"]
        if outcome is Outcome.RECORD_ONLY and should_raise_alarm(detection.event_type, detection.confidence,
                                                                 self.config.threshold) \
                and now - self._ignored_logged.get(detection.source, float("-inf")) >= IGNORED_EVENT_INTERVAL_SECONDS:
            self._ignored_logged[detection.source] = now
            self._safe_event("detection_ignored", at=now, actor=f"node:{detection.source}", cause=detection.source,
                             state=before.state.value)
        if after.state is not before.state:
            self._announce(after, now)
        return outcome

    def tick(self, now: Optional[float] = None) -> Optional[dict]:
        """Applies an elapsed timer. An entry delay that runs out sounds the siren as the system actor; if that
        siren command fails it is retried on every tick while the alarm stays triggered."""
        now = self.clock() if now is None else now
        before, after = self.repo.update(lambda s: advance(s, now, self.config), actor=SYSTEM_ACTOR.name)
        if after.state is not before.state:
            self._announce(after, now)
        if before.state is AlarmState.PENDING and after.state is AlarmState.TRIGGERED:
            self._siren_owed = True
        elif after.state is not AlarmState.TRIGGERED:
            self._siren_owed = False
        if not self._siren_owed:
            return None
        result = self._drive("activar_sirena", {"duracion_segundos": DEFAULT_SIREN_SECONDS}, SYSTEM_ACTOR)
        self._siren_owed = result.get("status") != "success"
        return result

    # -- helpers ---------------------------------------------------------------------------------
    def _announce(self, status: AlarmStatus, now: float) -> dict:
        described = self.describe(status, now)
        try:
            self.broadcast.publish({"event": "alarm_state", "alarm": described})
        except Exception:  # noqa: BLE001 - the dashboard notification is best effort
            logger.warning("Could not broadcast the alarm state")
        return described

    def _drive(self, tool: str, args: dict, actor: Actor) -> dict:
        """Physical action through the choke point; an adapter crash becomes a failed result, never a 500
        after the alarm state already changed."""
        try:
            return self.physical_action(tool, args, actor=actor)
        except Exception as exc:  # noqa: BLE001 - reported in the result
            logger.exception("Physical action %s raised", tool)
            return {"status": "failed", "message": str(exc)}

    def _safe_event(self, kind: str, **kwargs) -> None:
        try:
            self.repo.record_event(kind, **kwargs)
        except Exception:  # noqa: BLE001 - a timeline row must never block the alarm
            logger.exception("Could not record alarm event %s", kind)
