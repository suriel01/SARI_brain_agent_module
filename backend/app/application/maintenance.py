"""Periodic state maintenance run by the background worker (never by an HTTP request).

- Siren auto-off: the siren flag drops ``SIREN_AUTO_OFF_SECONDS`` after the last alert.
- Ghost-node pruning: live entries of unregistered nodes silent for ``GHOST_NODE_SECONDS`` are removed.
- Expired operational log entries are purged.
"""
from dataclasses import dataclass, field
from typing import Iterable, List

from .ports import StateRepository

SIREN_AUTO_OFF_SECONDS = 30
GHOST_NODE_SECONDS = 60.0
# Kept when no eye node is registered, so the default Jetson never counts as a ghost.
DEFAULT_REGISTERED_NODES = ("Jetson-PTZ_1",)


@dataclass
class MaintenanceResult:
    siren_expired: bool = False
    pruned_nodes: List[str] = field(default_factory=list)


def run_maintenance(state: StateRepository, registered_node_ids: Iterable[str], now: float) -> MaintenanceResult:
    registered = set(registered_node_ids) or set(DEFAULT_REGISTERED_NODES)
    state.purge_expired_logs()
    expired = state.expire_siren(now, SIREN_AUTO_OFF_SECONDS)
    pruned = state.prune_nodes(now - GHOST_NODE_SECONDS, keep=registered)
    return MaintenanceResult(siren_expired=expired, pruned_nodes=list(pruned))
