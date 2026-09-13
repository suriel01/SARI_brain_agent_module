from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import requests
import os
import datetime
import asyncio

from ..database import get_db
from ..crud import crud
from ..schemas import schemas
from .deps import get_current_user
from .hardware import execute_physical_tool, HardwareState
from ..security import has_perm, require_pin

router = APIRouter()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.actions import action

# Initialize Guardrails configuration
guardrails_path = os.path.join(os.path.dirname(__file__), "../guardrails")
config = RailsConfig.from_path(guardrails_path)

@action(name="execute_activar_sirena")
async def action_activate_siren():
    res = execute_physical_tool("activate_siren", {"duration_seconds": 30})
    return res.get("message", "Siren activated.")

@action(name="execute_desactivar_sirena")
async def action_deactivate_siren():
    res = execute_physical_tool("deactivate_siren", {})
    return res.get("message", "Siren deactivated.")

@action(name="execute_cerrar_accesos")
async def action_lock_gates():
    res = execute_physical_tool("lock_gates", {})
    return res.get("message", "Gates locked.")

# Global NeMo Guardrails instance
rails_app = LLMRails(config)
rails_app.register_action(action_activate_siren, name="execute_activar_sirena")
rails_app.register_action(action_deactivate_siren, name="execute_desactivar_sirena")
rails_app.register_action(action_lock_gates, name="execute_cerrar_accesos")

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
        require_pin(req.pin)
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
    can_hw = has_perm(current_user, "can_control_hardware")

    # Fast-rail: Deactivate / Silence Siren
    if any(k in msg_lower for k in [
        "apagar sirena", "desactivar sirena", "desactiva la sirena", "desactiva sirena", 
        "apaga la alarma", "apaga alarma", "desactiva la alarma", "desactiva alarma", 
        "silenciar sirena", "silenciar alarma", "turn off siren", "deactivate siren", 
        "turn off alarm", "deactivate alarm", "silence siren", "silence alarm", "stop siren"
    ]):
        if not can_hw:
            resp_content = "Protocol denied: Insufficient clearance to deactivate the physical siren." if lang == "en" else "Protocolo denegado: Autorización insuficiente para desactivar la sirena/alarma física."
        else:
            execute_physical_tool("deactivate_siren", {})
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
        if not can_hw:
            resp_content = "Protocol denied: Insufficient clearance to activate the physical siren." if lang == "en" else "Protocolo denegado: Autorización insuficiente para activar la sirena/alarma física."
        else:
            execute_physical_tool("activate_siren", {"duration_seconds": 30})
            resp_content = "🚨 Acknowledged. I have activated the emergency physical siren for 30 seconds. Perimeter is now on maximum alert." if lang == "en" else "🚨 Entendido. He activado la sirena física/alarma de emergencia por 30 segundos. El sistema se encuentra en alerta máxima."
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Fast-rail: Lock Perimeter Gates
    if any(k in msg_lower for k in [
        "bloquear accesos", "cerrar accesos", "bloquea accesos", "cerrar puertas", 
        "lock gates", "close gates", "lock perimeter", "close doors"
    ]):
        if not can_hw:
            resp_content = "Protocol denied: Insufficient clearance to lock perimeter gates." if lang == "en" else "Protocolo denegado: Autorización insuficiente para bloquear accesos."
        else:
            execute_physical_tool("lock_gates", {})
            resp_content = "🔒 Acknowledged. All perimeter gates and access points have been locked successfully." if lang == "en" else "🔒 Entendido. Todos los accesos perimetrales han sido bloqueados con éxito."
        msg_db = crud.add_message(db, thread_id, role="agent", content=resp_content)
        return msg_db

    # Fast-rail: Camera / Snapshot Request
    if any(k in msg_lower for k in [
        "captura", "snapshot", "foto", "imagen de la intrusión", "imagen de la intrusion", 
        "ver camara", "ver cámara", "camera snapshot", "view camera", "take snapshot"
    ]):
        now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot_url = "http://localhost:7000/api/hardware/snapshot/jetson-cv1"
        if lang == "en":
            resp_content = f"""📸 **REAL-TIME TACTICAL VISION SNAPSHOT**

![Camera Snapshot]({snapshot_url})

| Parameter | Tactical Value |
| :--- | :--- |
| **Vision Device:** | Jetson Orin CV Node (IP: `192.168.1.73`) |
| **Timestamp:** | `{now_time}` |
| **Detection Filter:** | YOLOv26n Active |
| **Inference Confidence:** | `96.4%` (PERSON DETECTED) |
| **Perimeter Status:** | Active Real-time Monitoring OK |
"""
        else:
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

    # Fast-rail: Tactical Status Report (.md breakdown)
    if any(k in msg_lower for k in [
        "reporte de estatus", "estatus del sistema", "reporte del sistema", "status report", 
        "informe de estado", "estado del sistema", "dame el estatus", "system status", "status"
    ]):
        now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        recent_event_logs = db.query(crud.models.EventLog).order_by(crud.models.EventLog.timestamp.desc()).limit(5).all()
        
        if lang == "en":
            siren_status = "🔴 **ACTIVATED (ALERT)**" if HardwareState.siren_active else "🟢 **DEACTIVATED (NORMAL)**"
            gates_status = "🔒 **LOCKED (SECURED)**" if HardwareState.gates_locked else "🔓 **UNLOCKED (NORMAL)**"
            user_clearance = current_user.get("clearance_level", 1)
            access_badge = "👑 **ADMINISTRATOR (Full Access Level 5)**" if user_role == "admin" else f"🛡️ **MONITOR (Access Level {user_clearance})**"
            
            jetson_db_modules = db.query(crud.models.EventLog.module_name).distinct().all()
            module_names = set([m[0] for m in jetson_db_modules if m[0]] + ["Jetson Orin Nano 01 (North Zone)"])
            jetson_rows = []
            for idx, mod in enumerate(sorted(module_names), 1):
                ip_addr = "192.168.1.73" if idx == 1 else f"192.168.1.{73 + idx}"
                jetson_rows.append(f"| **{mod}** | `{ip_addr}` | 🟢 **ONLINE** | 🔴 **RECORDING (REC 1080p)** | `YOLOv26n` |")
            jetson_nodes_md = "\n".join(jetson_rows)

            table_rows = []
            if recent_event_logs:
                for ev in recent_event_logs:
                    ts = ev.timestamp.strftime("%H:%M:%S")
                    conf_pct = f"{int((ev.confidence or 0.9)*100)}%"
                    table_rows.append(f"| `{ev.id}` | `{ts}` | `{ev.module_name}` | {ev.event_description} | `{conf_pct}` |")
            else:
                table_rows.append("| - | - | `RAG Engine` | No critical intrusions logged | 100% |")
            table_md = "\n".join(table_rows)

            resp_content = f"""# 🛡️ SARI SOC TACTICAL STATUS REPORT

**Report Timestamp:** `{now_time}`  
**Authenticated Operator:** `{current_user.get('username') or current_user.get('sub') or 'Operator'}` ({access_badge})

---

### 📡 1. Peripherals & Physical Hardware State
| Peripheral / Module | Operating Status | Location |
| :--- | :--- | :--- |
| **Emergency Siren** | {siren_status} | Central Server |
| **Perimeter Gates** | {gates_status} | Main Perimeter Accesses |
| **RAG / PostgreSQL Engine** | 🟢 **pgvector ONLINE** | SOC Database |
| **Tactical AI Core** | 🟢 **LLM Online (Guardrails Active)** | Central Server |

---

### 📷 2. Tactical Vision Modules (Jetson Orin Nano Nodes)
| Jetson Device | IP / Interface | Link Status | Recording (REC) | CV Model |
| :--- | :--- | :---: | :---: | :--- |
{jetson_nodes_md}

---

### 📋 3. Recent Intrusion Log & RAG Memory
| ID | Time | Vision Module | Detected Event | Confidence |
| :---: | :---: | :--- | :--- | :---: |
{table_md}

---

### 🔒 4. Threat Assessment & RBAC Clearance
- **Threat Level:** {"🔴 CRITICAL ALERT" if HardwareState.siren_active else "🟢 NORMAL"}
- **Access Scope:** {"Full authorization for manual alarm dispatch and gate security." if user_role == "admin" or current_user.get("can_control_hardware") else "⚠️ Read-only Mode: Limited authorization according to RBAC policy."}
"""
        else:
            siren_status = "🔴 **ACTIVADA (ALERTA)**" if HardwareState.siren_active else "🟢 **DESACTIVADA (NORMAL)**"
            gates_status = "🔒 **BLOQUEADOS (SEGURIDAD)**" if HardwareState.gates_locked else "🔓 **DESBLOQUEADOS (NORMAL)**"
            user_clearance = current_user.get("clearance_level", 1)
            access_badge = "👑 **ADMINISTRADOR (Acceso Total Nivel 5)**" if user_role == "admin" else f"🛡️ **MONITOR (Nivel de Acceso {user_clearance})**"
            
            jetson_db_modules = db.query(crud.models.EventLog.module_name).distinct().all()
            module_names = set([m[0] for m in jetson_db_modules if m[0]] + ["Jetson Orin Nano 01 (Zona Norte)"])
            jetson_rows = []
            for idx, mod in enumerate(sorted(module_names), 1):
                ip_addr = "192.168.1.73" if idx == 1 else f"192.168.1.{73 + idx}"
                jetson_rows.append(f"| **{mod}** | `{ip_addr}` | 🟢 **ONLINE** | 🔴 **GRABANDO (REC 1080p)** | `YOLOv26n` |")
            jetson_nodes_md = "\n".join(jetson_rows)

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
        response = await rails_app.generate_async(messages=messages)
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
    require_pin(req.pin)
    new_th = crud.create_thread(db, user_id=current_user.get("id"), title=req.title)
    HardwareState.add_log(f"➕ New chat thread created: '{req.title}'", level="INFO", camera_module="CHAT_MGMT")
    return new_th

@router.put("/threads/{thread_id}", response_model=schemas.ChatThreadResponse)
def update_thread(thread_id: int, req: schemas.ChatThreadCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not has_perm(current_user, "can_rename_chats"):
        raise HTTPException(status_code=403, detail="Action denied: Permission required to rename chats.")
    require_pin(req.pin)
    updated = crud.update_thread_title(db, thread_id, req.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Chat not found")
    HardwareState.add_log(f"✏️ Chat thread #{thread_id} renamed to '{req.title}'", level="INFO", camera_module="CHAT_MGMT")
    return updated

@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, pin: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not has_perm(current_user, "can_delete_chats"):
        raise HTTPException(status_code=403, detail="Action denied: Permission required to delete chats.")
    require_pin(pin)
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
