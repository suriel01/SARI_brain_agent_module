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
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:14b")

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

    msg_lower = req.message.lower()

    # Hardware Fast-rail (desactivar DEBE ir antes que activar para evitar coincidencias parciales)
    if any(k in msg_lower for k in ["apagar sirena", "desactivar sirena", "desactiva la sirena", "desactiva sirena", "apaga la alarma", "silenciar sirena"]):
        if user_role != "admin":
            resp_content = "Protocolo denegado: Autorización insuficiente para desactivar sirena."
        else:
            res = execute_physical_tool("desactivar_sirena", {})
            resp_content = res.get("message", "Sirena apagada.")
        
        msg_db = crud.add_message(db, thread_id, role="system", content=resp_content)
        return msg_db

    if any(k in msg_lower for k in ["activar sirena", "activa la sirena", "activa sirena", "enciende la alarma", "sonar alarma"]):
        if user_role != "admin":
            resp_content = "Protocolo denegado: Autorización insuficiente para activar sirena."
        else:
            res = execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
            resp_content = res.get("message", "Sirena activada.")
        
        msg_db = crud.add_message(db, thread_id, role="system", content=resp_content)
        return msg_db

    if any(k in msg_lower for k in ["bloquear accesos", "cerrar accesos", "bloquea accesos", "cerrar puertas"]):
        if user_role != "admin":
            resp_content = "Protocolo denegado: Autorización insuficiente para bloquear accesos."
        else:
            res = execute_physical_tool("cerrar_accesos", {})
            resp_content = res.get("message", "Accesos bloqueados.")
        
        msg_db = crud.add_message(db, thread_id, role="system", content=resp_content)
        return msg_db

    # LLM Request
    system_prompt = f"""Eres SARI (Sistema Autónomo de Respuesta a Intrusiones).
El usuario con el que hablas tiene el rol de: {user_role}.
Tu función es monitorear el perímetro, controlar alarmas y proveer estatus de seguridad.
Responde con fluidez a preguntas sobre tu identidad y reportes.
NO tienes acceso a internet. Rechaza peticiones fuera del ámbito de seguridad."""

    # Historial (últimos 5 mensajes)
    history = db.query(crud.models.ChatMessage).filter(crud.models.ChatMessage.thread_id == thread_id).order_by(crud.models.ChatMessage.timestamp.desc()).limit(6).all()
    history.reverse()

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[:-1]:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": req.message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2}
    }

    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=30.0)
        if res.status_code == 200:
            llm_text = res.json().get("message", {}).get("content", "")
        else:
            llm_text = f"Error del motor Ollama (HTTP {res.status_code})"
    except Exception as e:
        llm_text = f"Error de conexión LLM: {e}"

    msg_db = crud.add_message(db, thread_id, role="agent", content=llm_text)
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
    return crud.create_thread(db, user_id=current_user.get("id"), title=req.title)

@router.put("/threads/{thread_id}", response_model=schemas.ChatThreadResponse)
def update_thread(thread_id: int, req: schemas.ChatThreadCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin" and not current_user.get("can_rename_chats"):
        raise HTTPException(status_code=403, detail="Acción denegada: No tienes permiso para renombrar hilos.")
    updated = crud.update_thread_title(db, thread_id, req.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Thread no encontrado")
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
    return {"status": "success", "message": "Thread eliminado"}

@router.get("/threads/{thread_id}/messages", response_model=List[schemas.ChatMessageResponse])
def get_thread_messages(thread_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    thread = crud.get_thread(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread no encontrado")
    return thread.messages
