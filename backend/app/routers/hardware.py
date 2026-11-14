"""Hardware HTTP adapter: `/api/hardware/*` routes.

The choke point itself lives in `app.application.physical_actions` (wired in `app.adapters.composition`);
the names below are re-exported so `app.routers.hardware` stays the import path every channel uses.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import requests
import os
import time
import logging
from ..models import models
from ..database import SessionLocal
from .deps import get_current_user, require_hardware_user
from ..security import has_perm, require_pin
from ..node_auth import require_node
from ..domain.actions import ACTIVATE_SIREN, DEACTIVATE_SIREN, LOCK_GATES, UNLOCK_GATES, ALL_TOOLS, canonical_action
from ..domain.actors import Actor
from ..adapters.actuators.siren_http import SIRENA_SERVICE_URL
from ..adapters.persistence.audit_sql import record_physical_action
from ..adapters.state.legacy_facade import HardwareState  # deprecated facade, re-exported for tests only
from ..adapters.composition import boot_time, execute_physical_tool, state
from ..domain.state import NODE_TELEMETRY_FIELDS
from ..application.maintenance import GHOST_NODE_SECONDS, SIREN_AUTO_OFF_SECONDS  # noqa: F401  (re-exported)

__all__ = [
    "ACTIVATE_SIREN", "ALL_TOOLS", "Actor", "DEACTIVATE_SIREN", "HardwareState", "LOCK_GATES", "NODE_TELEMETRY_FIELDS",
    "SIRENA_SERVICE_URL", "UNLOCK_GATES", "boot_time", "canonical_action", "execute_physical_tool",
    "record_physical_action", "router",
]

router = APIRouter()

logger = logging.getLogger("sari_hardware")


class NodeTelemetryPayload(BaseModel):
    node_id: str
    name: Optional[str] = None
    ip: Optional[str] = None
    ram_used_gb: Optional[float] = None
    ram_total_gb: Optional[float] = None
    cpu_load_pct: Optional[float] = None
    gpu_load_pct: Optional[float] = None
    temp_c: Optional[float] = None
    fps: Optional[float] = None
    link_status: Optional[str] = None


def get_system_gpu_telemetry() -> Dict[str, Any]:
    """Queries host GPU, CPU and Ollama model telemetry. Values that could not be read are None (S15)."""
    telemetry: Dict[str, Any] = {
        "gpu_name": None,
        "gpu_load_pct": None,
        "vram_used_gb": None,
        "vram_total_gb": None,
        "vram_pct": None,
        "gpu_temp_c": None,
        "cpu_load_pct": None,
        "cpu_temp_c": None,
        "model_name": os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),  # configured model, not a measurement
        "model_status": None,
        "has_gpu": False,
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
        telemetry["has_gpu"] = True
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
                telemetry["has_gpu"] = True
        except Exception:
            pass

    # Read CPU load and CPU temperature with psutil
    try:
        import psutil
        telemetry["cpu_load_pct"] = float(psutil.cpu_percent(interval=None))
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
            telemetry["model_status"] = "Not loaded"
            if running_models:
                m0 = running_models[0]
                telemetry["model_name"] = m0.get("name", telemetry["model_name"])
                telemetry["model_status"] = "Active in VRAM"
                size_vram = m0.get("size_vram", 0)
                if size_vram > 0 and (telemetry["vram_used_gb"] or 0.0) < 0.5:
                    telemetry["vram_used_gb"] = round(size_vram / (1024 ** 3), 2)
                    if telemetry["vram_total_gb"]:
                        telemetry["vram_pct"] = round((telemetry["vram_used_gb"] / telemetry["vram_total_gb"]) * 100, 1)
    except Exception:
        pass

    return telemetry

@router.get("/state")
def get_state(current_user: dict = Depends(get_current_user)):
    """Read-only view of the live state. Siren auto-off and ghost-node pruning run in the worker."""
    now = time.time()
    nodes_list = []
    active_count = 0
    for node in state.list_nodes().values():
        last_seen = node.get("last_seen", 0)
        is_online = (node.get("is_online") is not False) and ((now - last_seen) < 120.0)
        if is_online:
            active_count += 1
        nodes_list.append({
            **node,
            "is_online": is_online,
            "seconds_since_last_seen": round(now - last_seen, 1)
        })

    snapshot = state.snapshot()
    return {
        "siren_active": snapshot.siren_active,
        "gates_locked": snapshot.gates_locked,
        "gates_simulated": True,
        "alert_count": snapshot.alert_count,
        "last_alert_thread_id": snapshot.last_alert_thread_id,
        "logs": state.list_logs(),
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
        "ip": payload.ip,
        **{field: getattr(payload, field) for field in NODE_TELEMETRY_FIELDS},
        "last_seen": time.time(),
        "is_online": True
    }
    state.put_node(node_id, node_data)
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
        if state.actuators().siren_active:
            return execute_physical_tool("deactivate_siren", {}, actor=actor)
        return execute_physical_tool("activate_siren", {"duration_seconds": 30}, actor=actor)
    if action in ("toggle_accesos", "toggle_gates"):
        if state.actuators().gates_locked:
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
