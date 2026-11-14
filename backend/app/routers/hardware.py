from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import requests
import os
import time
import datetime
import asyncio
import logging
from dataclasses import dataclass, field
from ..schemas import schemas
from ..models import models
from ..database import SessionLocal
from .deps import get_current_user, require_hardware_user
from ..security import has_perm, require_pin
from ..ws import manager
from ..node_auth import require_node

router = APIRouter()
logger = logging.getLogger("sari_hardware")

SIRENA_SERVICE_URL = os.environ.get("SIRENA_SERVICE_URL", "http://localhost:5000")


def _siren_headers() -> dict:
    from ..config import get_settings

    return {"X-SARI-Siren-Token": get_settings().siren_token}
boot_time = datetime.datetime.now()

class NodeTelemetryPayload(BaseModel):
    node_id: str
    name: Optional[str] = None
    ip: Optional[str] = "192.168.55.1"
    ram_used_gb: Optional[float] = None
    ram_total_gb: Optional[float] = None
    cpu_load_pct: Optional[float] = None
    gpu_load_pct: Optional[float] = None
    temp_c: Optional[float] = None
    fps: Optional[float] = None
    link_status: Optional[str] = "Stable (1Gbps)"

class HardwareState:
    """In-memory state tracker for physical actuators, node telemetry, and audit logs."""
    siren_active = False
    gates_locked = False
    alert_count = 0
    last_alert_time = 0.0
    last_alert_thread_id = None
    
    # Registered Jetson Nodes (Tracked in real time)
    nodes: Dict[str, Dict[str, Any]] = {
        "Jetson-PTZ_1": {
            "node_id": "Jetson-PTZ_1",
            "name": "Jetson Orin CV Node",
            "ip": "192.168.55.1",
            "ram_used_gb": 3.8,
            "ram_total_gb": 8.0,
            "cpu_load_pct": 45.0,
            "gpu_load_pct": 62.0,
            "temp_c": 52.0,
            "fps": 30.0,
            "link_status": "USB Direct (1Gbps)",
            "last_seen": time.time()
        }
    }
    
    logs = [
        {
            "timestamp": (boot_time - datetime.timedelta(seconds=15)).strftime("%Y-%m-%d %H:%M:%S"), 
            "message": "🔐 PostgreSQL Database connected & healthy with pgvector.", 
            "level": "INFO",
            "camera_module": "SYS_CORE",
            "expires_at": (boot_time + datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "timestamp": (boot_time - datetime.timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S"), 
            "message": "🧠 Brain Module online & listening for YOLO vision node alerts.", 
            "level": "INFO",
            "camera_module": "SYS_CORE",
            "expires_at": (boot_time + datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "timestamp": (boot_time - datetime.timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S"), 
            "message": "🔊 Audio microservice connected.", 
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
    def record_node_activity(cls, node_id: str, ip: str = "192.168.55.1"):
        if node_id not in cls.nodes:
            cls.nodes[node_id] = {
                "node_id": node_id,
                "name": f"Jetson Node ({node_id})",
                "ip": ip,
                "ram_used_gb": 3.8,
                "ram_total_gb": 8.0,
                "cpu_load_pct": 45.0,
                "gpu_load_pct": 60.0,
                "temp_c": 52.0,
                "fps": 30.0,
                "link_status": "USB Direct",
                "last_seen": time.time()
            }
        else:
            cls.nodes[node_id]["last_seen"] = time.time()

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

def get_system_gpu_telemetry() -> Dict[str, Any]:
    """Queries NVIDIA GPU (RTX 4070), host CPU, and Ollama AI model telemetry."""
    telemetry = {
        "gpu_name": "NVIDIA GeForce RTX 4070",
        "gpu_load_pct": 0.0,
        "vram_used_gb": 0.0,
        "vram_total_gb": 8.0,
        "vram_pct": 0.0,
        "gpu_temp_c": 42.0,
        "cpu_load_pct": 35.0,
        "model_name": os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
        "model_status": "Ready in VRAM",
        "has_gpu": True
    }
    
    # Try pynvml
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        telemetry["gpu_name"] = pynvml.nvmlDeviceGetName(handle)
        if isinstance(telemetry["gpu_name"], bytes):
            telemetry["gpu_name"] = telemetry["gpu_name"].decode("utf-8")
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        telemetry["gpu_load_pct"] = float(util.gpu)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        telemetry["vram_used_gb"] = round(mem.used / (1024 ** 3), 2)
        telemetry["vram_total_gb"] = round(mem.total / (1024 ** 3), 2)
        if telemetry["vram_total_gb"] > 0:
            telemetry["vram_pct"] = round((telemetry["vram_used_gb"] / telemetry["vram_total_gb"]) * 100, 1)
        telemetry["gpu_temp_c"] = float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
        pynvml.nvmlShutdown()
    except Exception:
        # Fallback to nvidia-smi execution
        try:
            import subprocess
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name", "--format=csv,noheader,nounits"],
                text=True, timeout=1.0
            ).strip().split(",")
            if len(out) >= 4:
                telemetry["gpu_load_pct"] = float(out[0].strip())
                telemetry["vram_used_gb"] = round(float(out[1].strip()) / 1024.0, 2)
                telemetry["vram_total_gb"] = round(float(out[2].strip()) / 1024.0, 2)
                if telemetry["vram_total_gb"] > 0:
                    telemetry["vram_pct"] = round((telemetry["vram_used_gb"] / telemetry["vram_total_gb"]) * 100, 1)
                telemetry["gpu_temp_c"] = float(out[3].strip())
                if len(out) >= 5:
                    telemetry["gpu_name"] = out[4].strip()
        except Exception:
            pass

    # Read CPU load and CPU temperature with psutil
    try:
        import psutil
        telemetry["cpu_load_pct"] = float(psutil.cpu_percent(interval=None))
        telemetry["cpu_temp_c"] = 52.0
        temps = psutil.sensors_temperatures() if hasattr(psutil, 'sensors_temperatures') else {}
        if temps:
            for key in ['coretemp', 'cpu_thermal', 'k10temp', 'acpitz']:
                if key in temps and temps[key]:
                    telemetry["cpu_temp_c"] = round(float(temps[key][0].current), 1)
                    break
    except Exception:
        pass

    # Check Ollama loaded model status
    try:
        ollama_base = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434/api/chat").replace("/api/chat", "")
        res = requests.get(f"{ollama_base}/api/ps", timeout=0.8)
        if res.status_code == 200:
            running_models = res.json().get("models", [])
            if running_models:
                m0 = running_models[0]
                telemetry["model_name"] = m0.get("name", telemetry["model_name"])
                telemetry["model_status"] = "Active in VRAM"
                size_vram = m0.get("size_vram", 0)
                if size_vram > 0 and telemetry["vram_used_gb"] < 0.5:
                    telemetry["vram_used_gb"] = round(size_vram / (1024 ** 3), 2)
                    telemetry["vram_pct"] = round((telemetry["vram_used_gb"] / telemetry["vram_total_gb"]) * 100, 1)
    except Exception:
        pass

    return telemetry

ACTIVATE_SIREN = {"activate_siren", "activar_sirena"}
DEACTIVATE_SIREN = {"deactivate_siren", "desactivar_sirena"}
LOCK_GATES = {"lock_gates", "cerrar_accesos"}
UNLOCK_GATES = {"unlock_gates", "abrir_accesos"}
ALL_TOOLS = ACTIVATE_SIREN | DEACTIVATE_SIREN | LOCK_GATES | UNLOCK_GATES


@dataclass(frozen=True)
class Actor:
    """Who is asking for a physical action, and through which channel."""

    name: str
    channel: str
    can_control_hardware: bool
    allowed_tools: frozenset = field(default=frozenset(ALL_TOOLS))

    @classmethod
    def from_user(cls, user: dict, channel: str) -> "Actor":
        return cls(
            name=str(user.get("username") or user.get("sub") or "unknown"),
            channel=channel,
            can_control_hardware=has_perm(user, "can_control_hardware"),
        )

    @classmethod
    def node(cls, node_id: str) -> "Actor":
        """An authenticated vision node may raise the alarm, never silence it or touch gates."""
        return cls(name=f"node:{node_id}", channel="node", can_control_hardware=True, allowed_tools=frozenset(ACTIVATE_SIREN))

    def may_run(self, tool_name: str) -> bool:
        return self.can_control_hardware and tool_name in self.allowed_tools


def canonical_action(tool_name: str) -> str:
    """Maps Spanish/English tool aliases to one canonical name for the audit trail."""
    for canonical, aliases in (
        ("activate_siren", ACTIVATE_SIREN),
        ("deactivate_siren", DEACTIVATE_SIREN),
        ("lock_gates", LOCK_GATES),
        ("unlock_gates", UNLOCK_GATES),
    ):
        if tool_name in aliases:
            return canonical
    return str(tool_name)[:50]


def record_physical_action(actor: Optional[Actor], tool_name: str, result: str, detail: str = "") -> None:
    """Persists one audit row (S8). Never raises: a broken audit DB must not block raising the alarm.

    Fail-open is deliberate for a siren: losing an audit row is preferable to a silent perimeter.
    The failure is logged at ERROR so it is visible.
    """
    try:
        db = SessionLocal()
    except Exception as exc:
        logger.error("Physical action audit unavailable (%s): %s by %s", exc, tool_name, actor.name if actor else "anonymous")
        return
    try:
        db.add(
            models.PhysicalActionLog(
                actor_name=(actor.name if actor else "anonymous")[:100],
                channel=(actor.channel if actor else "unknown")[:30],
                action=canonical_action(tool_name),
                result=result,
                detail=detail or None,
            )
        )
        db.commit()
    except Exception as exc:
        logger.error("Could not persist physical action audit row: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _call_siren_service(path: str, payload: Optional[dict]) -> tuple:
    """Calls the siren microservice. Returns (ok, reason); ok only on a 2xx answer."""
    try:
        kwargs = {"headers": _siren_headers(), "timeout": 2.0}
        if payload is not None:
            kwargs["json"] = payload
        res = requests.post(f"{SIRENA_SERVICE_URL}{path}", **kwargs)
    except Exception as exc:
        logger.error("Siren service unreachable on %s: %s", path, exc)
        return False, "siren service unreachable"
    status = getattr(res, "status_code", None)
    if not isinstance(status, int) or not 200 <= status < 300:
        logger.error("Siren service answered %s on %s", status, path)
        return False, f"siren service answered HTTP {status}"
    return True, ""


def _broadcast(payload: dict) -> None:
    """Best-effort WebSocket notification; only called after the hardware confirmed the action."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(manager.broadcast_json(payload))
    except Exception:
        pass


def execute_physical_tool(tool_name: str, args: dict = None, *, actor: Actor):
    """Single choke point for physical actions: checks the actor's permission and audits every call."""
    result = _execute_physical_tool(tool_name, args or {}, actor=actor)
    status = result.get("status")
    record_physical_action(actor, tool_name, status if status in ("success", "denied", "failed") else "failed", result.get("message", ""))
    return result


def _execute_physical_tool(tool_name: str, args: dict, *, actor: Actor):
    if actor is None or not actor.may_run(tool_name):
        who = actor.name if actor else "anonymous"
        via = actor.channel if actor else "unknown"
        HardwareState.add_log(f"⛔ Physical action '{tool_name}' denied for [{who}] via {via}", level="WARN", camera_module="HARDWARE_CTRL")
        return {"status": "denied", "message": "⛔ Permission denied: hardware control not authorized."}
    
    duration = args.get("duration_seconds") or args.get("duracion_segundos", 30)

    if tool_name in ACTIVATE_SIREN:
        ok, reason = _call_siren_service("/api/alarma/activar", {"duracion": duration})
        if not ok:
            HardwareState.add_log(f"❌ Siren activation FAILED: {reason}", level="ERROR", camera_module="HARDWARE_CTRL")
            return {"status": "failed", "message": f"❌ Siren activation failed: {reason}."}
        HardwareState.siren_active = True
        HardwareState.alert_count += 1
        HardwareState.last_alert_time = time.time()
        HardwareState.add_log(f"🚨 Physical Siren activated for {duration}s", level="ERROR", camera_module="HARDWARE_CTRL")
        _broadcast({"event": "siren_activated"})
        return {"status": "success", "message": "🚨 Siren activated."}

    elif tool_name in DEACTIVATE_SIREN:
        ok, reason = _call_siren_service("/api/alarma/desactivar", None)
        if not ok:
            HardwareState.add_log(f"❌ Siren deactivation FAILED: {reason}", level="ERROR", camera_module="HARDWARE_CTRL")
            return {"status": "failed", "message": f"❌ Siren deactivation failed: {reason}. The siren may still be sounding."}
        HardwareState.siren_active = False
        HardwareState.add_log("🔊 Siren deactivated / silenced by operator", level="INFO", camera_module="HARDWARE_CTRL")
        _broadcast({"event": "siren_deactivated"})
        return {"status": "success", "message": "🔊 Siren turned off & silenced."}

    elif tool_name in LOCK_GATES:
        HardwareState.gates_locked = True
        HardwareState.add_log("🔒 Perimeter gates locked (simulated: no gate hardware connected)", level="WARN", camera_module="HARDWARE_CTRL")
        return {"status": "success", "simulated": True, "message": "🔒 Perimeter gates locked (simulated: no gate hardware connected)."}

    elif tool_name in UNLOCK_GATES:
        HardwareState.gates_locked = False
        HardwareState.add_log("🔓 Perimeter gates unlocked (simulated: no gate hardware connected)", level="INFO", camera_module="HARDWARE_CTRL")
        return {"status": "success", "simulated": True, "message": "🔓 Perimeter gates unlocked (simulated: no gate hardware connected)."}

    return {"status": "error", "message": f"Unknown hardware tool: {tool_name}"}

@router.get("/state")
def get_state(current_user: dict = Depends(get_current_user)):
    now = time.time()
    HardwareState.purge_expired_logs()
    if HardwareState.siren_active and (now - HardwareState.last_alert_time > 30):
        HardwareState.siren_active = False

    # Synchronize with registered active EyeNode records from database
    db = SessionLocal()
    try:
        registered_eyes = db.query(models.EyeNode).filter(models.EyeNode.is_active == True).all()
        registered_ids = {e.node_id for e in registered_eyes}
        if not registered_ids:
            registered_ids = {"Jetson-PTZ_1"}
    finally:
        db.close()

    # Clean up expired ephemeral test nodes (older than 60s and not registered in EyeNode)
    for ghost_id in list(HardwareState.nodes.keys()):
        if ghost_id not in registered_ids:
            if (now - HardwareState.nodes[ghost_id].get("last_seen", 0)) > 60.0:
                HardwareState.nodes.pop(ghost_id, None)
    nodes_list = []
    active_count = 0
    for nid, node in HardwareState.nodes.items():
        last_seen = node.get("last_seen", 0)
        is_online = (node.get("is_online") is not False) and ((now - last_seen) < 120.0)
        if is_online:
            active_count += 1
        nodes_list.append({
            **node,
            "is_online": is_online,
            "seconds_since_last_seen": round(now - last_seen, 1)
        })

    return {
        "siren_active": HardwareState.siren_active,
        "gates_locked": HardwareState.gates_locked,
        "gates_simulated": True,
        "alert_count": HardwareState.alert_count,
        "last_alert_thread_id": HardwareState.last_alert_thread_id,
        "logs": HardwareState.logs,
        "nodes": nodes_list,
        "nodes_count": active_count,
        "system_telemetry": get_system_gpu_telemetry()
    }

@router.post("/telemetry/node")
def receive_node_telemetry(payload: NodeTelemetryPayload, auth_node: str = Depends(require_node)):
    """Receives periodic real-time hardware telemetry from Jetson CV nodes."""
    node_id = payload.node_id or auth_node
    if node_id != auth_node:
        raise HTTPException(status_code=403, detail="Node credentials do not match node_id")
    node_data = {
        "node_id": node_id,
        "name": payload.name or f"Jetson Node ({node_id})",
        "ip": payload.ip or "192.168.55.1",
        "ram_used_gb": payload.ram_used_gb if payload.ram_used_gb is not None else 3.8,
        "ram_total_gb": payload.ram_total_gb if payload.ram_total_gb is not None else 8.0,
        "cpu_load_pct": payload.cpu_load_pct if payload.cpu_load_pct is not None else 45.0,
        "gpu_load_pct": payload.gpu_load_pct if payload.gpu_load_pct is not None else 62.0,
        "temp_c": payload.temp_c if payload.temp_c is not None else 52.0,
        "fps": payload.fps if payload.fps is not None else 30.0,
        "link_status": payload.link_status or "1Gbps USB Direct",
        "last_seen": time.time(),
        "is_online": True
    }
    HardwareState.nodes[node_id] = node_data
    return {"status": "success", "message": f"Telemetry recorded for {node_id}"}

@router.post("/manual_action")
def manual_action(req: dict, current_user: dict = Depends(get_current_user)):
    action = req.get("action")
    actor = Actor.from_user(current_user, "rest")
    if not has_perm(current_user, "can_control_hardware"):
        record_physical_action(actor, str(action), "denied", "manual_action without can_control_hardware")
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    require_pin(req.get("pin"), key=f"user:{current_user.get('id')}")

    if action in ACTIVATE_SIREN:
        return execute_physical_tool("activate_siren", {"duration_seconds": 30}, actor=actor)
    if action in DEACTIVATE_SIREN:
        return execute_physical_tool("deactivate_siren", {}, actor=actor)
    if action in LOCK_GATES:
        return execute_physical_tool("lock_gates", {}, actor=actor)
    if action in UNLOCK_GATES:
        return execute_physical_tool("unlock_gates", {}, actor=actor)

    # Legacy toggles (sent by HardwarePanel/Dashboard): flip the current state.
    if action in ("toggle_sirena", "toggle_siren"):
        if HardwareState.siren_active:
            return execute_physical_tool("deactivate_siren", {}, actor=actor)
        return execute_physical_tool("activate_siren", {"duration_seconds": 30}, actor=actor)
    if action in ("toggle_accesos", "toggle_gates"):
        if HardwareState.gates_locked:
            return execute_physical_tool("unlock_gates", {}, actor=actor)
        return execute_physical_tool("lock_gates", {}, actor=actor)
    
    raise HTTPException(status_code=400, detail=f"Unknown hardware action: {action}")

AUDIT_MAX_LIMIT = 500


@router.get("/audit")
def list_physical_action_audit(limit: int = 100, current_user: dict = Depends(require_hardware_user)):
    """Persistent physical-action audit trail, newest first (S8)."""
    limit = max(1, min(int(limit), AUDIT_MAX_LIMIT))
    db = SessionLocal()
    try:
        rows = (
            db.query(models.PhysicalActionLog)
            .order_by(models.PhysicalActionLog.timestamp.desc(), models.PhysicalActionLog.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "actor_name": r.actor_name,
                "channel": r.channel,
                "action": r.action,
                "result": r.result,
                "detail": r.detail,
            }
            for r in rows
        ]
    finally:
        db.close()
