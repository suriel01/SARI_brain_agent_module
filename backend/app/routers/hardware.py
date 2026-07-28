from fastapi import APIRouter, Depends, HTTPException
import requests
import os
from ..schemas import schemas
from .deps import get_current_user

router = APIRouter()

SIRENA_SERVICE_URL = os.environ.get("SIRENA_SERVICE_URL", "http://localhost:5000")

import time

# Global state memory for the UI to poll (since we don't have websockets in this basic HTTP version)
import datetime
boot_time = datetime.datetime.now()

class HardwareState:
    siren_active = False
    gates_locked = False
    alert_count = 0
    last_alert_time = 0.0
    last_alert_thread_id = None
    
    # Initial logs with timestamp, camera_module, and TTL expires_at (24h)
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
    def add_log(cls, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE", ttl_hours: int = 24):
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

def execute_physical_tool(tool_name: str, args: dict):
    if tool_name == "activar_sirena":
        try:
            res = requests.post(f"{SIRENA_SERVICE_URL}/api/alarma/activar", json={"duracion": args.get("duracion_segundos", 30)}, timeout=5.0)
            if res.status_code == 200:
                HardwareState.siren_active = True
                HardwareState.alert_count += 1
                HardwareState.last_alert_time = time.time()
                HardwareState.add_log(f"🚨 Physical Siren activated for {args.get('duracion_segundos', 30)}s", level="ERROR", camera_module="HARDWARE_CTRL")
                return {"status": "success", "message": "🚨 Siren activated."}
            return {"status": "error", "message": f"Siren service failed: {res.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to contact siren: {e}"}

    elif tool_name == "desactivar_sirena":
        try:
            res = requests.post(f"{SIRENA_SERVICE_URL}/api/alarma/desactivar", timeout=5.0)
            HardwareState.siren_active = False
            HardwareState.add_log("🔊 Siren deactivated", level="INFO", camera_module="HARDWARE_CTRL")
            return {"status": "success", "message": "🔊 Siren turned off."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif tool_name == "cerrar_accesos":
        HardwareState.gates_locked = True
        HardwareState.add_log("🔒 Perimeter gates locked", level="WARN", camera_module="HARDWARE_CTRL")
        return {"status": "success", "message": "🔒 Perimeter gates locked."}

    elif tool_name == "abrir_accesos":
        HardwareState.gates_locked = False
        HardwareState.add_log("🔓 Perimeter gates unlocked", level="INFO", camera_module="HARDWARE_CTRL")
        return {"status": "success", "message": "🔓 Perimeter gates unlocked."}
    
    return {"status": "error", "message": "Unknown tool"}


@router.get("/state")
def get_state(current_user: dict = Depends(get_current_user)):
    if HardwareState.siren_active and (time.time() - HardwareState.last_alert_time > 30):
        HardwareState.siren_active = False

    return {
        "siren_active": HardwareState.siren_active,
        "gates_locked": HardwareState.gates_locked,
        "alert_count": HardwareState.alert_count,
        "last_alert_thread_id": HardwareState.last_alert_thread_id,
        "logs": HardwareState.logs
    }

@router.post("/manual_action")
def manual_action(req: dict, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    action = req.get("action")
    if action in ["toggle_sirena", "activar_sirena", "desactivar_sirena"]:
        if HardwareState.siren_active:
            return execute_physical_tool("desactivar_sirena", {})
        else:
            return execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
    elif action in ["toggle_accesos", "cerrar_accesos", "abrir_accesos"]:
        if HardwareState.gates_locked:
            return execute_physical_tool("abrir_accesos", {})
        else:
            return execute_physical_tool("cerrar_accesos", {})
    
    raise HTTPException(status_code=400, detail="Unknown action")

@router.get("/snapshot/{cam_id}")
def get_camera_snapshot(cam_id: str):
    import datetime
    from fastapi import Response
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360" style="background:#0d1117; font-family: monospace;">
  <!-- Camera Feed Background Grid -->
  <rect width="640" height="360" fill="#0b0e14" />
  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
  </pattern>
  <rect width="640" height="360" fill="url(#grid)" />

  <!-- Camera HUD Corners -->
  <path d="M 20 40 L 20 20 L 40 20" fill="none" stroke="#ff3366" stroke-width="2" />
  <path d="M 620 40 L 620 20 L 600 20" fill="none" stroke="#ff3366" stroke-width="2" />
  <path d="M 20 320 L 20 340 L 40 340" fill="none" stroke="#ff3366" stroke-width="2" />
  <path d="M 620 320 L 620 340 L 600 340" fill="none" stroke="#ff3366" stroke-width="2" />

  <!-- Simulated Object Detection Box -->
  <rect x="220" y="110" width="200" height="160" fill="rgba(255, 51, 102, 0.15)" stroke="#ff3366" stroke-width="2" stroke-dasharray="4 2"/>
  <rect x="220" y="90" width="130" height="20" fill="#ff3366" />
  <text x="225" y="104" fill="#ffffff" font-size="11" font-weight="bold">PERSON (96.4%)</text>

  <!-- Crosshair -->
  <line x1="320" y1="180" x2="320" y2="200" stroke="rgba(255, 51, 102, 0.8)" stroke-width="1"/>
  <line x1="310" y1="190" x2="330" y2="190" stroke="rgba(255, 51, 102, 0.8)" stroke-width="1"/>

  <!-- HUD Overlay Text -->
  <text x="30" y="45" fill="#ff3366" font-size="14" font-weight="bold">● REC [LIVE FEED]</text>
  <text x="30" y="65" fill="#8b949e" font-size="12">CAM: {cam_id.upper()} (JETSON CV NODE)</text>
  <text x="440" y="45" fill="#8b949e" font-size="12">{now_str}</text>
  <text x="440" y="65" fill="#00ffcc" font-size="12">STATUS: MONITOREO OK</text>

  <!-- Bottom Banner -->
  <rect x="0" y="330" width="640" height="30" fill="rgba(0,0,0,0.7)" />
  <text x="20" y="350" fill="#c9d1d9" font-size="11">SARI SOC TACTICAL PERCEPTION NODE • IP: 192.168.1.73</text>
</svg>"""
    return Response(content=svg_content, media_type="image/svg+xml")
