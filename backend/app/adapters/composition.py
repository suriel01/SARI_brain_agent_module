"""Composition root: wires the use cases to their concrete adapters for this process."""
from typing import Optional

from ..application.physical_actions import ExecutePhysicalAction
from ..domain.actors import Actor
from .actuators.siren_http import HttpSiren
from .persistence.audit_sql import SqlAudit
from .realtime.ws_broadcast import WsBroadcast
from .state.memory_state import MemoryState

state = MemoryState()
broadcaster = WsBroadcast()
physical_action = ExecutePhysicalAction(siren=HttpSiren(), audit=SqlAudit(), broadcast=broadcaster, state=state)


def execute_physical_tool(tool_name: str, args: Optional[dict] = None, *, actor: Optional[Actor]):
    """Single choke point for physical actions: checks the actor's permission and audits every call."""
    return physical_action(tool_name, args, actor=actor)
