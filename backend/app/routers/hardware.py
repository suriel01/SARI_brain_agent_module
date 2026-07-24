from fastapi import APIRouter, Depends, HTTPException
import requests
import os
from ..schemas import schemas
from .deps import get_current_user

router = APIRouter()

SIRENA_SERVICE_URL = os.environ.get("SIRENA_SERVICE_URL", "http://localhost:5000")

# Global state memory for the UI to poll (since we don't have websockets in this basic HTTP version)
class HardwareState:
    siren_active = False
    alert_count = 0
    logs = []

    @classmethod
    def add_log(cls, msg, level="INFO"):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        cls.logs.insert(0, {"timestamp": ts, "message": msg, "level": level})
        if len(cls.logs) > 50:
            cls.logs.pop()

def execute_physical_tool(tool_name: str, args: dict):
    if tool_name == "activar_sirena":
        try:
            res = requests.post(f"{SIRENA_SERVICE_URL}/api/alarma/activar", json={"duracion": args.get("duracion_segundos", 30)}, timeout=5.0)
            if res.status_code == 200:
                HardwareState.siren_active = True
                HardwareState.add_log(f"🚨 Sirena física activada por {args.get('duracion_segundos', 30)}s", "ERROR")
                return {"status": "success", "message": "🚨 Sirena activada."}
            return {"status": "error", "message": f"Servicio sirena falló: {res.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Fallo al contactar sirena: {e}"}

    elif tool_name == "desactivar_sirena":
        try:
            res = requests.post(f"{SIRENA_SERVICE_URL}/api/alarma/desactivar", timeout=5.0)
            HardwareState.siren_active = False
            HardwareState.add_log("🔊 Sirena desactivada", "INFO")
            return {"status": "success", "message": "🔊 Sirena apagada."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif tool_name == "cerrar_accesos":
        HardwareState.add_log("🔒 Accesos bloqueados", "INFO")
        return {"status": "success", "message": "🔒 Portones bloqueados."}
    
    return {"status": "error", "message": "Tool desconocida"}


@router.get("/state")
def get_state(current_user: dict = Depends(get_current_user)):
    return {
        "siren_active": HardwareState.siren_active,
        "alert_count": HardwareState.alert_count,
        "logs": HardwareState.logs
    }

@router.post("/manual_action")
def manual_action(req: dict, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    # En una app real validaríamos el pin aquí
    
    action = req.get("action")
    if action == "activar_sirena":
        return execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
    elif action == "desactivar_sirena":
        return execute_physical_tool("desactivar_sirena", {})
    elif action == "cerrar_accesos":
        return execute_physical_tool("cerrar_accesos", {})
    
    raise HTTPException(status_code=400, detail="Acción desconocida")
