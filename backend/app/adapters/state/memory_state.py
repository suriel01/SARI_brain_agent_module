"""Process-local StateRepository for development and tests. Production uses `SqlStateRepository`.

Nothing here survives a restart or is shared between processes; a lock keeps each write atomic
within the process.
"""
import datetime
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

from ...domain.state import (
    LOG_CAPACITY, LOG_TIME_FORMAT, LOG_TTL_HOURS, NODE_TELEMETRY_FIELDS, RUNTIME_FIELDS, ActuatorState,
    RuntimeState, new_node,
)

__all__ = ["MemoryState", "NODE_TELEMETRY_FIELDS"]


class MemoryState:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._lock = threading.RLock()
        self._runtime: Dict[str, Any] = {field: getattr(RuntimeState(), field) for field in RUNTIME_FIELDS}
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._logs: List[Dict[str, Any]] = []  # newest first; expires_at kept as datetime

    # -- actuators and counters
    def snapshot(self) -> RuntimeState:
        with self._lock:
            return RuntimeState(**self._runtime)

    def actuators(self) -> ActuatorState:
        return self.snapshot().actuators

    def siren_activated(self, at: float) -> None:
        with self._lock:
            self._runtime.update(siren_active=True, alert_count=self._runtime["alert_count"] + 1, last_alert_time=at)

    def siren_deactivated(self) -> None:
        with self._lock:
            self._runtime["siren_active"] = False

    def expire_siren(self, now: float, after_seconds: float) -> bool:
        with self._lock:
            if self._runtime["siren_active"] and self._runtime["last_alert_time"] < now - after_seconds:
                self._runtime["siren_active"] = False
                return True
            return False

    def set_gates_locked(self, locked: bool) -> None:
        with self._lock:
            self._runtime["gates_locked"] = bool(locked)

    def set_last_alert_thread(self, thread_id: int) -> None:
        with self._lock:
            self._runtime["last_alert_thread_id"] = thread_id

    def overwrite_runtime(self, **fields: Any) -> None:
        unknown = set(fields) - set(RUNTIME_FIELDS)
        if unknown:
            raise AttributeError(f"Unknown runtime state field(s): {sorted(unknown)}")
        with self._lock:
            self._runtime.update(fields)

    # -- nodes
    def record_node_activity(self, node_id: str, ip: Optional[str] = None) -> None:
        now = self._clock()
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                self._nodes[node_id] = new_node(node_id, ip, now)
                return
            node["last_seen"] = now
            if ip:
                node["ip"] = ip

    def put_node(self, node_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._nodes[node_id] = dict(data)

    def merge_node(self, node_id: str, fields: Dict[str, Any], *, create: bool = False) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                if not create:
                    return False
                self._nodes[node_id] = {}
            self._nodes[node_id].update(fields)
            return True

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            node = self._nodes.get(node_id)
            return dict(node) if node is not None else None

    def list_nodes(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {node_id: dict(node) for node_id, node in sorted(self._nodes.items())}

    def remove_node(self, node_id: str) -> None:
        with self._lock:
            self._nodes.pop(node_id, None)

    def clear_nodes(self) -> None:
        with self._lock:
            self._nodes.clear()

    def prune_nodes(self, older_than: float, keep: Iterable[str]) -> List[str]:
        keep = set(keep)
        with self._lock:
            stale = [
                node_id for node_id, node in self._nodes.items()
                if node_id not in keep and not (isinstance(node.get("last_seen"), (int, float)) and node["last_seen"] >= older_than)
            ]
            for node_id in stale:
                del self._nodes[node_id]
            return stale

    # -- operational log
    def add_log(self, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE") -> None:
        now = datetime.datetime.now()
        with self._lock:
            self._purge(now)
            self._logs.insert(0, {
                "created_at": now, "expires_at": now + datetime.timedelta(hours=LOG_TTL_HOURS),
                "message": msg, "level": level, "camera_module": camera_module,
            })
            del self._logs[LOG_CAPACITY:]

    def list_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        now = datetime.datetime.now()
        with self._lock:
            live = [entry for entry in self._logs if entry["expires_at"] > now]
        live = live[:limit] if limit is not None else live
        return [
            {
                "timestamp": entry["created_at"].strftime(LOG_TIME_FORMAT),
                "message": entry["message"],
                "level": entry["level"],
                "camera_module": entry["camera_module"],
                "expires_at": entry["expires_at"].strftime(LOG_TIME_FORMAT),
            }
            for entry in live
        ]

    def purge_expired_logs(self) -> None:
        with self._lock:
            self._purge(datetime.datetime.now())

    def _purge(self, now: datetime.datetime) -> None:
        self._logs = [entry for entry in self._logs if entry["expires_at"] > now]
