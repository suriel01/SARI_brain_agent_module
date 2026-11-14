from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import requests
import os
import datetime
import time
import contextvars

from ..database import get_db
from ..crud import crud
from ..schemas import schemas
from .deps import get_current_user
from .hardware import Actor, execute_physical_tool, HardwareState
from ..security import has_perm, require_pin

router = APIRouter()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.actions import action

# Initialize Guardrails configuration
guardrails_path = os.path.join(os.path.dirname(__file__), "../guardrails")
config = RailsConfig.from_path(guardrails_path)

# Actor on whose behalf the LLM is acting. Unset means no one: every physical action is denied.
current_actor: contextvars.ContextVar = contextvars.ContextVar("sari_llm_actor", default=None)


@action(name="execute_activar_sirena")
async def action_activate_siren():
    res = execute_physical_tool("activate_siren", {"duration_seconds": 30}, actor=current_actor.get())
    return res.get("message", "")

@action(name="execute_desactivar_sirena")
async def action_deactivate_siren():
    res = execute_physical_tool("deactivate_siren", {}, actor=current_actor.get())
    return res.get("message", "")

@action(name="execute_cerrar_accesos")
async def action_lock_gates():
    res = execute_physical_tool("lock_gates", {}, actor=current_actor.get())
    return res.get("message", "")

# Global NeMo Guardrails instance
rails_app = LLMRails(config)
rails_app.register_action(action_activate_siren, name="execute_activar_sirena")
rails_app.register_action(action_deactivate_siren, name="execute_desactivar_sirena")
rails_app.register_action(action_lock_gates, name="execute_cerrar_accesos")

def _failure_reply(result: dict, lang: str) -> str:
    detail = result.get("message", "")
    if lang == "en":
        return f"⚠️ The physical action could not be completed: {detail}"
    return f"⚠️ La acción física no pudo completarse: {detail}"


NODE_ONLINE_WINDOW_S = 120.0


def _node_rows(db: Session, lang: str) -> str:
    """One row per known vision node from live telemetry and registered eyes; unknown values say so."""
    unknown = "unknown" if lang == "en" else "desconocido"
    now = time.time()
    registered = {e.node_id: e for e in db.query(crud.models.EyeNode).all()}
    rows = []
    for node_id in sorted(set(HardwareState.nodes) | set(registered)):
        live = HardwareState.nodes.get(node_id, {})
        eye = registered.get(node_id)
        last_seen = live.get("last_seen") or 0.0
        online = bool(live) and live.get("is_online") is not False and (now - last_seen) < NODE_ONLINE_WINDOW_S
        ip = live.get("ip") or (eye.ip if eye else None) or unknown
        name = (eye.name if eye else None) or live.get("name") or node_id
        link = "🟢 **ONLINE**" if online else "🔴 **OFFLINE**"
        seen = f"{int(now - last_seen)}s" if last_seen else unknown
        rows.append(f"| **{name}** (`{node_id}`) | `{ip}` | {link} | {seen} |")
    if not rows:
        return "| - | - | - | - |"
    return "\n".join(rows)


def _status_report(db: Session, current_user: dict, lang: str) -> str:
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_role = current_user.get("role")
    operator = current_user.get("username") or current_user.get("sub") or "Operator"
    can_hw = has_perm(current_user, "can_control_hardware")
    recent = db.query(crud.models.EventLog).order_by(crud.models.EventLog.timestamp.desc()).limit(5).all()
    nodes_md = _node_rows(db, lang)
    event_rows = [
        f"| `{ev.id}` | `{ev.timestamp.strftime('%H:%M:%S') if ev.timestamp else '-'}` | `{ev.module_name}` | {ev.event_description} | "
        f"`{f'{int(ev.confidence * 100)}%' if ev.confidence is not None else '-'}` |"
        for ev in recent
    ]

    if lang == "en":
        siren_status = "🔴 **ACTIVATED (ALERT)**" if HardwareState.siren_active else "🟢 **DEACTIVATED (NORMAL)**"
        gates_status = "🔒 **LOCKED**" if HardwareState.gates_locked else "🔓 **UNLOCKED**"
        badge = "👑 **ADMINISTRATOR**" if user_role == "admin" else f"🛡️ **MONITOR (Access Level {current_user.get('clearance_level', 1)})**"
        events_md = "\n".join(event_rows) or "| - | - | - | No intrusions logged | - |"
        return f"""# 🛡️ SARI SOC TACTICAL STATUS REPORT

**Report Timestamp:** `{now_time}`  
**Authenticated Operator:** `{operator}` ({badge})

---

### 📡 1. Physical Actuators
| Peripheral | Operating Status | Note |
| :--- | :--- | :--- |
| **Emergency Siren** | {siren_status} | Last state confirmed by the siren service |
| **Perimeter Gates** | {gates_status} | Simulated: no gate hardware connected |

---

### 📷 2. Vision Nodes (live telemetry)
| Node | IP | Link | Last seen |
| :--- | :--- | :---: | :---: |
{nodes_md}

---

### 📋 3. Recent Detections
| ID | Time | Vision Module | Detected Event | Confidence |
| :---: | :---: | :--- | :--- | :---: |
{events_md}

---

### 🔒 4. Threat Assessment & RBAC Clearance
- **Threat Level:** {"🔴 CRITICAL ALERT" if HardwareState.siren_active else "🟢 NORMAL"}
- **Access Scope:** {"Authorized for manual alarm dispatch and gate control." if can_hw else "⚠️ Read-only Mode: Limited authorization according to RBAC policy."}
"""

    siren_status = "🔴 **ACTIVADA (ALERTA)**" if HardwareState.siren_active else "🟢 **DESACTIVADA (NORMAL)**"
    gates_status = "🔒 **BLOQUEADOS**" if HardwareState.gates_locked else "🔓 **DESBLOQUEADOS**"
    badge = "👑 **ADMINISTRADOR**" if user_role == "admin" else f"🛡️ **MONITOR (Nivel de Acceso {current_user.get('clearance_level', 1)})**"
    events_md = "\n".join(event_rows) or "| - | - | - | Sin intrusiones registradas | - |"
    return f"""# 🛡️ REPORTE TÁCTICO DE ESTATUS SARI SOC

**Fecha y Hora del Reporte:** `{now_time}`  
**Operador Autenticado:** `{operator}` ({badge})

---

### 📡 1. Actuadores Físicos
| Periférico | Estado Operativo | Nota |
| :--- | :--- | :--- |
| **Sirena de Emergencia** | {siren_status} | Último estado confirmado por el servicio de sirena |
| **Portones Perimetrales** | {gates_status} | Simulado: no hay hardware de portones conectado |

---

### 📷 2. Nodos de Visión (telemetría en vivo)
| Nodo | IP | Conexión | Última señal |
| :--- | :--- | :---: | :---: |
{nodes_md}

---

### 📋 3. Detecciones Recientes
| ID | Hora | Módulo Visión | Evento Detectado | Confianza |
| :---: | :---: | :--- | :--- | :---: |
{events_md}

---

### 🔒 4. Evaluación de Seguridad & RBAC
- **Nivel de Amenaza:** {"🔴 ALERTA CRÍTICA" if HardwareState.siren_active else "🟢 NORMAL"}
- **Acceso a Funciones:** {"Autorizado para disparo manual de alarma y control de portones." if can_hw else "⚠️ Modo Lectura: Autorización limitada según política RBAC."}
"""


@router.post("", response_model=schemas.ChatMessageResponse)
@router.post("/", response_model=schemas.ChatMessageResponse)
async def chat_endpoint(req: schemas.ChatRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    user_role = current_user.get("role")
    lang = req.language if req.language in ["en", "es"] else "es"
    
    # Manage conversation threads
    thread_id = req.thread_id
    if not thread_id:
        if not has_perm(current_user, "can_create_chats"):
            err_msg = "Permission denied: Clearance required to create chat threads." if lang == "en" else "Acción denegada: Permiso requerido para crear hilos."
            raise HTTPException(status_code=403, detail=err_msg)
        require_pin(req.pin, key=f"user:{current_user.get('id')}")
        thread = crud.create_thread(db, user_id=user_id, title=req.message[:30])
        thread_id = thread.id
    else:
        thread = crud.get_thread(db, thread_id)
        if not thread:
            err_msg = "Chat thread not found." if lang == "en" else "Thread no encontrado."
            raise HTTPException(status_code=404, detail=err_msg)

    # Save user message
    crud.add_message(db, thread_id, role="user", content=req.message)
    HardwareState.add_log(f"💬 User [{current_user.get('username') or 'Operator'}]: {req.message[:50]}", level="INFO", camera_module="CHAT_USER")
    msg_lower = req.message.lower()
    chat_actor = Actor.from_user(current_user, "chat")

    # Fast-rail: Deactivate / Silence Siren
    if any(k in msg_lower for k in [
        "apagar sirena", "desactivar sirena", "desactiva la sirena", "desactiva sirena", 
        "apaga la alarma", "apaga alarma", "desactiva la alarma", "desactiva alarma", 
        "silenciar sirena", "silenciar alarma", "turn off siren", "deactivate siren", 
        "turn off alarm", "deactivate alarm", "silence siren", "silence alarm", "stop siren"
    ]):
        result = execute_physical_tool("deactivate_siren", {}, actor=chat_actor)
        if result.get("status") == "denied":
            resp_content = "Protocol denied: Insufficient clearance to deactivate the physical siren." if lang == "en" else "Protocolo denegado: Autorización insuficiente para desactivar la sirena/alarma física."
        elif result.get("status") != "success":
            resp_content = _failure_reply(result, lang)
        else:
            resp_content = "🔊 Acknowledged. The physical alarm/siren has been deactivated. The system returns to normal monitoring state." if lang == "en" else "🔊 Entendido. La sirena física/alarma ha sido desactivada. El sistema vuelve a su estado de monitoreo normal."
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Fast-rail: Activate Siren
    if any(k in msg_lower for k in [
        "activar sirena", "activa la sirena", "activa sirena", "enciende la alarma", 
        "enciende alarma", "activa la alarma", "activa alarma", "prende la sirena", 
        "sonar alarma", "sonar sirena", "turn on siren", "activate siren", "turn on alarm", 
        "activate alarm", "sound alarm", "sound siren"
    ]):
        result = execute_physical_tool("activate_siren", {"duration_seconds": 30}, actor=chat_actor)
        if result.get("status") == "denied":
            resp_content = "Protocol denied: Insufficient clearance to activate the physical siren." if lang == "en" else "Protocolo denegado: Autorización insuficiente para activar la sirena/alarma física."
        elif result.get("status") != "success":
            resp_content = _failure_reply(result, lang)
        else:
            resp_content = "🚨 Acknowledged. I have activated the emergency physical siren for 30 seconds. Perimeter is now on maximum alert." if lang == "en" else "🚨 Entendido. He activado la sirena física/alarma de emergencia por 30 segundos. El sistema se encuentra en alerta máxima."
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Fast-rail: Lock Perimeter Gates
    if any(k in msg_lower for k in [
        "bloquear accesos", "cerrar accesos", "bloquea accesos", "cerrar puertas", 
        "lock gates", "close gates", "lock perimeter", "close doors"
    ]):
        result = execute_physical_tool("lock_gates", {}, actor=chat_actor)
        if result.get("status") == "denied":
            resp_content = "Protocol denied: Insufficient clearance to lock perimeter gates." if lang == "en" else "Protocolo denegado: Autorización insuficiente para bloquear accesos."
        elif result.get("status") != "success":
            resp_content = _failure_reply(result, lang)
        else:
            resp_content = "🔒 Acknowledged. Perimeter gates marked as locked (simulated: no gate hardware is connected)." if lang == "en" else "🔒 Entendido. Accesos perimetrales marcados como bloqueados (simulado: no hay hardware de portones conectado)."
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Fast-rail: Camera / Snapshot Request (latest real evidence frame, never a fabricated one)
    if any(k in msg_lower for k in [
        "captura", "snapshot", "foto", "imagen de la intrusión", "imagen de la intrusion", 
        "ver camara", "ver cámara", "camera snapshot", "view camera", "take snapshot"
    ]):
        latest = (
            db.query(crud.models.ChatMessage)
            .filter(crud.models.ChatMessage.snapshot.isnot(None))
            .order_by(crud.models.ChatMessage.id.desc())
            .first()
        )
        if latest:
            taken = latest.timestamp.strftime("%Y-%m-%d %H:%M:%S") if latest.timestamp else "unknown"
            if lang == "en":
                resp_content = f"📸 **Latest stored evidence frame** (captured `{taken}` UTC, thread #{latest.thread_id})."
            else:
                resp_content = f"📸 **Última captura de evidencia almacenada** (tomada `{taken}` UTC, hilo #{latest.thread_id})."
            msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content, snapshot=latest.snapshot)
        else:
            resp_content = (
                "📷 No evidence frame is stored yet. Live frames are available from the Eyes module."
                if lang == "en"
                else "📷 Aún no hay capturas de evidencia almacenadas. Las imágenes en vivo están en el módulo Ojos."
            )
            msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Fast-rail: Tactical Status Report (.md breakdown) built only from live state and the DB
    if any(k in msg_lower for k in [
        "reporte de estatus", "estatus del sistema", "reporte del sistema", "status report", 
        "informe de estado", "estado del sistema", "dame el estatus", "system status", "status"
    ]):
        resp_content = _status_report(db, current_user, lang)
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Fast-rail: Recent Events / RAG query
    if any(k in msg_lower for k in [
        "eventos", "detectado", "alertas", "historial", "recientemente", 
        "recent events", "qué pasó", "que paso", "what happened", "events", "alerts"
    ]):
        HardwareState.purge_expired_logs()
        recent_event_logs = db.query(crud.models.EventLog).order_by(crud.models.EventLog.timestamp.desc()).limit(5).all()
        hardware_logs = HardwareState.logs[:5]
        
        if lang == "en":
            lines = ["🔍 **SARI Security Events & Alert Summary:**\n"]
            if recent_event_logs:
                for ev in recent_event_logs:
                    lines.append(f"• [{ev.timestamp.strftime('%H:%M:%S')}] **{ev.module_name}**: {ev.event_description} (Confidence: {int((ev.confidence or 0.9)*100)}%)")
            else:
                lines.append("• No critical intrusions recorded in the RAG database.")
                
            if hardware_logs:
                lines.append("\n📋 **System Tactical Logs:**")
                for h in hardware_logs:
                    lines.append(f"• [{h['timestamp']}] ({h['level']}) {h['message']}")
        else:
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

    # Conversation History
    history = db.query(crud.models.ChatMessage).filter(crud.models.ChatMessage.thread_id == thread_id).order_by(crud.models.ChatMessage.timestamp.desc()).limit(6).all()
    history.reverse()

    messages = []
    for h in history[:-1]:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": req.message})

    llm_text = None

    # Try NeMo Guardrails (with language context)
    try:
        actor_token = current_actor.set(Actor.from_user(current_user, "llm"))
        try:
            response = await rails_app.generate_async(messages=messages)
        finally:
            current_actor.reset(actor_token)
        if isinstance(response, dict) and "content" in response:
            llm_text = response["content"]
        elif isinstance(response, str):
            llm_text = response
    except Exception as e:
        print(f"NeMo Guardrails skipped, falling back to direct Ollama: {e}")

    # Fallback to Ollama with language enforcement prompt
    if not llm_text:
        if lang == "en":
            system_prompt = f"You are SARI (Autonomous Intrusion Response System). Your user role is {user_role}. You monitor physical perimeter security and hardware controls. You MUST ALWAYS respond STRICTLY in English. Keep answers clear, tactical, professional, and helpful."
        else:
            system_prompt = f"Eres SARI (Sistema Autónomo de Respuesta a Intrusiones). Tu usuario es {user_role}. Monitoreas perímetro y seguridad física. Responde SIEMPRE estrictamente en ESPAÑOL de forma amable, clara, táctica y atenta."

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
                llm_text = f"Ollama engine error (HTTP {res.status_code})"
        except Exception as ex:
            llm_text = (
                "⚠️ The tactical AI engine (Ollama) is not responding at the moment. Please ensure it is running."
                if lang == "en"
                else "⚠️ El motor de IA táctica Ollama no está respondiendo en este momento. Por favor verifica que esté activo."
            )

    msg_db = crud.add_message(db, thread_id, role="agent", content=llm_text)
    HardwareState.add_log(f"🤖 Agent responded in Chat Thread #{thread_id} ({lang.upper()})", level="INFO", camera_module="CHAT_AGENT")
    return msg_db

@router.get("/threads", response_model=List[schemas.ChatThreadResponse])
def get_threads(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return crud.get_user_threads(db)

@router.post("/threads", response_model=schemas.ChatThreadResponse)
def create_thread_endpoint(req: schemas.ChatThreadCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not has_perm(current_user, "can_create_chats"):
        raise HTTPException(status_code=403, detail="Permission denied: Clearance required to create chat threads.")
    require_pin(req.pin, key=f"user:{current_user.get('id')}")
    new_th = crud.create_thread(db, user_id=current_user.get("id"), title=req.title)
    HardwareState.add_log(f"➕ New chat thread created: '{req.title}'", level="INFO", camera_module="CHAT_MGMT")
    return new_th

@router.put("/threads/{thread_id}", response_model=schemas.ChatThreadResponse)
def update_thread(thread_id: int, req: schemas.ChatThreadCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not has_perm(current_user, "can_rename_chats"):
        raise HTTPException(status_code=403, detail="Action denied: Permission required to rename chats.")
    require_pin(req.pin, key=f"user:{current_user.get('id')}")
    updated = crud.update_thread_title(db, thread_id, req.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Chat not found")
    HardwareState.add_log(f"✏️ Chat thread #{thread_id} renamed to '{req.title}'", level="INFO", camera_module="CHAT_MGMT")
    return updated

@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, pin: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not has_perm(current_user, "can_delete_chats"):
        raise HTTPException(status_code=403, detail="Action denied: Permission required to delete chats.")
    require_pin(pin, key=f"user:{current_user.get('id')}")
    deleted = crud.delete_thread(db, thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    HardwareState.add_log(f"🗑️ Chat thread #{thread_id} deleted by [{current_user.get('username')}]", level="WARN", camera_module="CHAT_MGMT")
    return {"status": "success", "message": "Thread deleted"}

@router.get("/threads/{thread_id}/messages", response_model=List[schemas.ChatMessageResponse])
def get_thread_messages(thread_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    thread = crud.get_thread(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread.messages
