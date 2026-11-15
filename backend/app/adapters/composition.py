"""Composition root: wires the use cases to their concrete adapters for this process.

`state` is the only place that chooses the StateRepository: the application database, so live state
is shared by every worker and survives restarts.
"""
import datetime
from typing import Optional

from ..application.alarm import AlarmService
from ..application.physical_actions import ExecutePhysicalAction
from ..application.supervision import Supervisor
from ..database import SessionLocal
from ..domain.actors import Actor
from .actuators.siren_http import HttpSiren
from .persistence.alarm_sql import SqlAlarmRepository
from .persistence.audit_sql import SqlAudit
from .persistence.state_sql import SqlStateRepository
from .realtime.ws_broadcast import WsBroadcast

boot_time = datetime.datetime.now()

state = SqlStateRepository(SessionLocal)
siren = HttpSiren()
broadcaster = WsBroadcast()
physical_action = ExecutePhysicalAction(siren=siren, audit=SqlAudit(), broadcast=broadcaster, state=state)
alarm = AlarmService(repo=SqlAlarmRepository(SessionLocal), physical_action=physical_action, audit=SqlAudit(),
                     broadcast=broadcaster)


def _telegram_notify(text: str) -> bool:
    from ..telegram.service import send_telegram_message

    return send_telegram_message(text)


supervisor = Supervisor(repo=alarm.repo, broadcast=broadcaster, notify=_telegram_notify, siren_health=siren.health)


def execute_physical_tool(tool_name: str, args: Optional[dict] = None, *, actor: Optional[Actor]):
    """Single choke point for physical actions: checks the actor's permission and audits every call."""
    return physical_action(tool_name, args, actor=actor)
