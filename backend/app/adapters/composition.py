"""Composition root: wires the use cases to their concrete adapters for this process.

`state` is the only place that chooses the StateRepository: the application database, so live state
is shared by every worker and survives restarts.
"""
import datetime
from typing import Optional

from ..application.physical_actions import ExecutePhysicalAction
from ..database import SessionLocal
from ..domain.actors import Actor
from .actuators.siren_http import HttpSiren
from .persistence.audit_sql import SqlAudit
from .persistence.state_sql import SqlStateRepository
from .realtime.ws_broadcast import WsBroadcast

boot_time = datetime.datetime.now()

state = SqlStateRepository(SessionLocal)
broadcaster = WsBroadcast()
physical_action = ExecutePhysicalAction(siren=HttpSiren(), audit=SqlAudit(), broadcast=broadcaster, state=state)


def execute_physical_tool(tool_name: str, args: Optional[dict] = None, *, actor: Optional[Actor]):
    """Single choke point for physical actions: checks the actor's permission and audits every call."""
    return physical_action(tool_name, args, actor=actor)
