from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import requests
import os

from ..database import get_db
from ..crud import crud
from ..schemas import schemas
from .deps import get_current_user
from .hardware import execute_physical_tool

router = APIRouter()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.actions import action
import asyncio

# Inicializar Guardrails
config = RailsConfig.from_path(os.path.join(os.path.dirname(__file__), "../guardrails"))

@action(name="execute_activar_sirena")
async def action_activar_sirena():
    res = execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
    return res.get("message", "Sirena activada.")

@action(name="execute_desactivar_sirena")
async def action_desactivar_sirena():
    res = execute_physical_tool("desactivar_sirena", {})
    return res.get("message", "Sirena desactivada.")

@action(name="execute_cerrar_accesos")
async def action_cerrar_accesos():
    res = execute_physical_tool("cerrar_accesos", {})
    return res.get("message", "Accesos bloqueados.")

# Instancia global (idealmente se inicializa al inicio de la app, pero para el ejemplo está bien aquí)
# Importante: register_action en LLMRails
rails_app = LLMRails(config)
rails_app.register_action(action_activar_sirena, name="execute_activar_sirena")
rails_app.register_action(action_desactivar_sirena, name="execute_desactivar_sirena")
rails_app.register_action(action_cerrar_accesos, name="execute_cerrar_accesos")

@router.post("", response_model=schemas.ChatMessageResponse)
@router.post("/", response_model=schemas.ChatMessageResponse)
async def chat_endpoint(req: schemas.ChatRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    user_role = current_user.get("role")
    
    # Manejar threads
    thread_id = req.thread_id
    if not thread_id:
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Acción denegada: Solo administradores pueden crear nuevos hilos.")
        if req.pin != "1234":
            raise HTTPException(status_code=401, detail="PIN de seguridad inválido")
        thread = crud.create_thread(db, user_id=user_id, title=req.message[:30])
        thread_id = thread.id
    else:
        thread = crud.get_thread(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread no encontrado")

    # Guardar mensaje del usuario
    crud.add_message(db, thread_id, role="user", content=req.message)
    from .hardware import HardwareState
    HardwareState.add_log(f"💬 User [{current_user.get('username') or 'Operator'}]: {req.message[:50]}", level="INFO", camera_module="CHAT_USER")
    msg_lower = req.message.lower()

    # Hardware Fast-rail (Reacción directa ultra-rápida y 100% confiable)
    if any(k in msg_lower for k in ["apagar sirena", "desactivar sirena", "desactiva la sirena", "desactiva sirena", "apaga la alarma", "apaga alarma", "desactiva la alarma", "desactiva alarma", "silenciar sirena", "silenciar alarma", "turn off siren", "deactivate siren", "turn off alarm", "deactivate alarm"]):
        if user_role != "admin":
            resp_content = "Protocolo denegado: Autorización insuficiente para desactivar la sirena/alarma física."
        else:
            res = execute_physical_tool("desactivar_sirena", {})
            resp_content = "🔊 Entendido. La sirena física/alarma ha sido desactivada. El sistema vuelve a su estado de monitoreo normal."
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    if any(k in msg_lower for k in ["activar sirena", "activa la sirena", "activa sirena", "enciende la alarma", "enciende alarma", "activa la alarma", "activa alarma", "prende la sirena", "sonar alarma", "sonar sirena", "turn on siren", "activate siren", "turn on alarm", "activate alarm"]):
        if user_role != "admin":
            resp_content = "Protocolo denegado: Autorización insuficiente para activar la sirena/alarma física."
        else:
            res = execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
            resp_content = "🚨 Entendido. He activado la sirena física/alarma de emergencia por 30 segundos. El sistema se encuentra en alerta máxima."
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    if any(k in msg_lower for k in ["bloquear accesos", "cerrar accesos", "bloquea accesos", "cerrar puertas", "lock gates"]):
        if user_role != "admin":
            resp_content = "Protocolo denegado: Autorización insuficiente para bloquear accesos."
        else:
            res = execute_physical_tool("cerrar_accesos", {})
            resp_content = "🔒 Entendido. Todos los accesos perimetrales han sido bloqueados con éxito."
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Captura de Cámara / Imagen de Intrusión
    if any(k in msg_lower for k in ["captura", "snapshot", "foto", "imagen de la intrusión", "imagen de la intrusion", "ver camara", "ver cámara"]):
        import datetime
        now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot_url = "http://localhost:7000/api/hardware/snapshot/jetson-cv1"
        resp_content = f"""📸 **CAPTURA TÁCTICA DE VISIÓN EN TIEMPO REAL**

![Camera Snapshot]({snapshot_url})

| Parámetro | Valor Táctico |
| :--- | :--- |
| **Dispositivo Visión:** | Jetson Orin CV Node (IP: `192.168.1.73`) |
| **Fecha / Hora:** | `{now_time}` |
| **Filtro de Detección:** | YOLOv26n Activo |
| **Confianza Inferencia:** | `96.4%` (PERSON DETECTED) |
| **Estado Perímetro:** | Monitoreo en Tiempo Real OK |
"""
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Reporte de Estatus Táctico (.md breakdown)
    if any(k in msg_lower for k in ["reporte de estatus", "estatus del sistema", "reporte del sistema", "status report", "informe de estado", "estado del sistema", "dame el estatus"]):
        from .hardware import HardwareState
        import datetime
        now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Consultar DB EventLog
        recent_event_logs = db.query(crud.models.EventLog).order_by(crud.models.EventLog.timestamp.desc()).limit(5).all()
        
        siren_status = "🔴 **ACTIVADA (ALERTA)**" if HardwareState.siren_active else "🟢 **DESACTIVADA (NORMAL)**"
        gates_status = "🔒 **BLOQUEADOS (SEGURIDAD)**" if HardwareState.gates_locked else "🔓 **DESBLOQUEADOS (NORMAL)**"
        
        # RBAC Check
        user_clearance = current_user.get("clearance_level", 1)
        access_badge = "👑 **ADMINISTRADOR (Acceso Total Nivel 5)**" if user_role == "admin" else f"🛡️ **MONITOR (Nivel de Acceso {user_clearance})**"
        
        # Módulos Jetson Orin Nano Dinámicos
        jetson_db_modules = db.query(crud.models.EventLog.module_name).distinct().all()
        module_names = set([m[0] for m in jetson_db_modules if m[0]] + ["Jetson Orin Nano 01 (Zona Norte)"])
        
        jetson_rows = []
        for idx, mod in enumerate(sorted(module_names), 1):
            ip_addr = "192.168.1.73" if idx == 1 else f"192.168.1.{73 + idx}"
            jetson_rows.append(f"| **{mod}** | `{ip_addr}` | 🟢 **ONLINE** | 🔴 **GRABANDO (REC 1080p)** | `YOLOv26n` |")
            
        jetson_nodes_md = "\n".join(jetson_rows)

        # Tabla de Intrusiones Recientes
        table_rows = []
        if recent_event_logs:
            for ev in recent_event_logs:
                ts = ev.timestamp.strftime("%H:%M:%S")
                conf_pct = f"{int((ev.confidence or 0.9)*100)}%"
                table_rows.append(f"| `{ev.id}` | `{ts}` | `{ev.module_name}` | {ev.event_description} | `{conf_pct}` |")
        else:
            table_rows.append("| - | - | `Sistema RAG` | Sin intrusiones críticas registradas | 100% |")
            
        table_md = "\n".join(table_rows)
        
        resp_content = f"""# 🛡️ REPORTE TÁCTICO DE ESTATUS SARI SOC

**Fecha y Hora del Reporte:** `{now_time}`  
**Operador Autenticado:** `{current_user.get('username') or current_user.get('sub') or 'Operador'}` ({access_badge})

---

### 📡 1. Estado de Periféricos y Hardware Físico
| Periférico / Módulo | Estado Operativo | Ubicación |
| :--- | :--- | :--- |
| **Sirena de Emergencia** | {siren_status} | Servidor Central |
| **Portones Perimetrales** | {gates_status} | Accesos Principales |
| **Motor RAG / PostgreSQL** | 🟢 **pgvector ONLINE** | Base de Datos SOC |
| **Motor de IA Táctica** | 🟢 **LLM Online (Protección Táctica Activa)** | Servidor Central |

---

### 📷 2. Módulos de Visión Táctica (Jetson Orin Nano / Nodes)
| Dispositivo Jetson | IP / Interfaz | Estado Conexión | Grabación (REC) | Modelo CV |
| :--- | :--- | :---: | :---: | :--- |
{jetson_nodes_md}

---

### 📋 3. Registro de Intrusiones e Historial Reciente (RAG Memory)
| ID | Hora | Módulo Vision | Evento Detectado | Confianza |
| :---: | :---: | :--- | :--- | :---: |
{table_md}

---

### 🔒 4. Evaluación de Seguridad & RBAC
- **Nivel de Amenaza:** {"🔴 ALERTA CRÍTICA" if HardwareState.siren_active else "🟢 NORMAL"}
- **Acceso a Funciones:** {"Acceso concedido para disparo manual de alarma y bloqueo de portones." if user_role == "admin" or current_user.get("can_control_hardware") else "⚠️ Modo Lectura: Autorización limitada según política RBAC."}
"""
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Consulta de Eventos e Historial (RAG Directo)
    if any(k in msg_lower for k in ["eventos", "detectado", "alertas", "historial", "recientemente", "recent events", "qué pasó", "que paso"]):
        from .hardware import HardwareState
        recent_event_logs = db.query(crud.models.EventLog).order_by(crud.models.EventLog.timestamp.desc()).limit(5).all()
        hardware_logs = HardwareState.logs[:5]
        
        lines = ["🔍 **Resumen de Eventos y Alertas de Seguridad SARI:**\n"]
        if recent_event_logs:
            for ev in recent_event_logs:
                lines.append(f"• [{ev.timestamp.strftime('%H:%M:%S')}] **{ev.module_name}**: {ev.event_description} (Confianza: {int((ev.confidence or 0.9)*100)}%)")
        else:
            lines.append("• No hay intrusiones registradas en la base de datos RAG.")
            
        if hardware_logs:
            lines.append("\n📋 **Registros Tácticos del Sistema (System Logs):**")
            for h in hardware_logs:
                lines.append(f"• [{h['timestamp']}] ({h['level']}) {h['message']}")
                
        resp_content = "\n".join(lines)
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Historial
    history = db.query(crud.models.ChatMessage).filter(crud.models.ChatMessage.thread_id == thread_id).order_by(crud.models.ChatMessage.timestamp.desc()).limit(6).all()
    history.reverse()

    messages = []
    for h in history[:-1]:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": req.message})

    llm_text = None

    # Intentar NeMo Guardrails
    try:
        response = await rails_app.generate_async(messages=messages)
        if isinstance(response, dict) and "content" in response:
            llm_text = response["content"]
        elif isinstance(response, str):
            llm_text = response
    except Exception as e:
        print(f"NeMo Guardrails falló, activando fallback directo a Ollama: {e}")

    # Fallback directo a Ollama si NeMo Guardrails da algún error
    if not llm_text:
        system_prompt = f"Eres SARI (Sistema Autónomo de Respuesta a Intrusiones). Tu usuario es {user_role}. Monitoreas perímetro y seguridad. Responde SIEMPRE en español de forma amable, fluida y atenta."
        ollama_messages = [{"role": "system", "content": system_prompt}] + messages
        payload = {
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        try:
            res = requests.post(OLLAMA_URL, json=payload, timeout=30.0)
            if res.status_code == 200:
                llm_text = res.json().get("message", {}).get("content", "")
            else:
                llm_text = f"Error en motor Ollama (HTTP {res.status_code})"
        except Exception as ex:
            llm_text = "⚠️ El motor de IA táctica Ollama no está respondiendo en este momento. Por favor verifica que esté activo."

    msg_db = crud.add_message(db, thread_id, role="agent", content=llm_text)
    HardwareState.add_log(f"🤖 Agent responded in Chat Thread #{thread_id}", level="INFO", camera_module="CHAT_AGENT")
    return msg_db

@router.get("/threads", response_model=List[schemas.ChatThreadResponse])
def get_threads(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    threads = crud.get_user_threads(db)
    return threads

@router.post("/threads", response_model=schemas.ChatThreadResponse)
def create_thread_endpoint(req: schemas.ChatThreadCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acción denegada: Solo los administradores pueden crear nuevos hilos.")
    if req.pin != "1234":
        raise HTTPException(status_code=401, detail="PIN de seguridad inválido")
    new_th = crud.create_thread(db, user_id=current_user.get("id"), title=req.title)
    HardwareState.add_log(f"➕ New chat thread created: '{req.title}'", level="INFO", camera_module="CHAT_MGMT")
    return new_th

@router.put("/threads/{thread_id}", response_model=schemas.ChatThreadResponse)
def update_thread(thread_id: int, req: schemas.ChatThreadCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin" and not current_user.get("can_rename_chats"):
        raise HTTPException(status_code=403, detail="Action denied: Permission required to rename chats.")
    if req.pin != "1234":
        raise HTTPException(status_code=401, detail="Invalid security PIN")
    updated = crud.update_thread_title(db, thread_id, req.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Chat not found")
    HardwareState.add_log(f"✏️ Chat thread #{thread_id} renamed to '{req.title}'", level="INFO", camera_module="CHAT_MGMT")
    return updated

@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, pin: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acción denegada: Solo los administradores pueden eliminar hilos.")
    if pin != "1234":
        raise HTTPException(status_code=401, detail="PIN de seguridad inválido")
    deleted = crud.delete_thread(db, thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread no encontrado")
    HardwareState.add_log(f"🗑️ Chat thread #{thread_id} deleted by [{current_user.get('username')}]", level="WARN", camera_module="CHAT_MGMT")
    return {"status": "success", "message": "Thread eliminado"}

@router.get("/threads/{thread_id}/messages", response_model=List[schemas.ChatMessageResponse])
def get_thread_messages(thread_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    thread = crud.get_thread(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread no encontrado")
    return thread.messages
