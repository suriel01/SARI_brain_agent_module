"""StatePort over the process-local `HardwareState` (replaced by a persisted repository in A2)."""
import datetime
import time
from typing import Any, Dict, Optional

from ...domain.state import ActuatorState

NODE_TELEMETRY_FIELDS = (
    "ram_used_gb", "ram_total_gb", "cpu_load_pct", "gpu_load_pct", "temp_c", "fps", "link_status",
)

boot_time = datetime.datetime.now()


class HardwareState:
    """In-memory state tracker for physical actuators, node telemetry, and audit logs."""
    siren_active = False
    gates_locked = False
    alert_count = 0
    last_alert_time = 0.0
    last_alert_thread_id = None

    # Vision nodes, keyed by node id. Filled only from real telemetry/alerts (S15: nothing invented).
    nodes: Dict[str, Dict[str, Any]] = {}

    logs = [
        {
            "timestamp": (boot_time - datetime.timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S"),
            "message": "🧠 Brain Module online & listening for YOLO vision node alerts.",
            "level": "INFO",
            "camera_module": "SYS_CORE",
            "expires_at": (boot_time + datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "timestamp": boot_time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "🛡️ SARI Physical Control System initialized.",
            "level": "INFO",
            "camera_module": "SYS_CORE",
            "expires_at": (boot_time + datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        }
    ]

    @classmethod
    def record_node_activity(cls, node_id: str, ip: Optional[str] = None):
        """Marks a node as seen. Telemetry it has not reported stays None (unknown)."""
        if node_id not in cls.nodes:
            cls.nodes[node_id] = {
                "node_id": node_id,
                "name": f"Jetson Node ({node_id})",
                "ip": ip,
                **{field: None for field in NODE_TELEMETRY_FIELDS},
                "last_seen": time.time(),
            }
        else:
            cls.nodes[node_id]["last_seen"] = time.time()
            if ip:
                cls.nodes[node_id]["ip"] = ip

    @classmethod
    def add_log(cls, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE", ttl_hours: int = 24):
        cls.purge_expired_logs()
        now = datetime.datetime.now()
        expires = now + datetime.timedelta(hours=ttl_hours)
        ts_str = now.strftime("%Y-%m-%d %H:%M:%S")
        exp_str = expires.strftime("%Y-%m-%d %H:%M:%S")
        cls.logs.insert(0, {
            "timestamp": ts_str,
            "message": msg,
            "level": level,
            "camera_module": camera_module,
            "expires_at": exp_str
        })
        if len(cls.logs) > 300:
            cls.logs.pop()

    @classmethod
    def purge_expired_logs(cls):
        now = datetime.datetime.now()
        kept = []
        for log in cls.logs:
            exp = log.get("expires_at")
            if not exp:
                kept.append(log)
                continue
            try:
                if datetime.datetime.strptime(exp, "%Y-%m-%d %H:%M:%S") > now:
                    kept.append(log)
            except ValueError:
                kept.append(log)
        cls.logs = kept


class MemoryState:
    """StatePort adapter. Reads and writes the `HardwareState` class so legacy readers stay in sync."""

    def __init__(self, store=HardwareState):
        self.store = store

    def actuators(self) -> ActuatorState:
        return ActuatorState(siren_active=self.store.siren_active, gates_locked=self.store.gates_locked)

    def siren_activated(self, at: float) -> None:
        self.store.siren_active = True
        self.store.alert_count += 1
        self.store.last_alert_time = at

    def siren_deactivated(self) -> None:
        self.store.siren_active = False

    def set_gates_locked(self, locked: bool) -> None:
        self.store.gates_locked = locked

    def add_log(self, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE") -> None:
        self.store.add_log(msg, level=level, camera_module=camera_module)

    def set_last_alert_thread(self, thread_id: int) -> None:
        self.store.last_alert_thread_id = thread_id

    def record_node_activity(self, node_id: str, ip: Optional[str] = None) -> None:
        self.store.record_node_activity(node_id, ip=ip)
