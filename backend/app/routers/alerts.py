from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import datetime
import requests
import os

from ..database import get_db, SessionLocal
from ..crud import crud
from .hardware import execute_physical_tool, HardwareState

router = APIRouter()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_EMBED_URL = OLLAMA_URL.replace("/api/chat", "/api/embeddings")
OLLAMA_EMBED_MODEL = "nomic-embed-text" # O qwen2.5-coder:14b si soporta embeddings, asumo nomic

class AlertEventRequest(BaseModel):
    module_name: str = "Jetson-CV-Node"
    event: str = "Detección perimetral"
    confidence: Optional[float] = 0.95
    auto_siren: Optional[bool] = True

from ..models import models

def save_event_and_embedding(module_name: str, event_desc: str, confidence: float):
    # Generar embedding asíncronamente
    embedding = None
    try:
        res = requests.post(OLLAMA_EMBED_URL, json={
            "model": OLLAMA_EMBED_MODEL,
            "prompt": f"[{module_name}] {event_desc}"
        }, timeout=10.0)
        if res.status_code == 200:
            embedding = res.json().get("embedding")
    except Exception as e:
        print(f"Error generando embedding: {e}")

    # Guardar en base de datos con una nueva sesión
    db = SessionLocal()
    try:
        new_event = models.EventLog(
            module_name=module_name,
            event_description=event_desc,
            confidence=confidence,
            embedding=embedding
        )
        db.add(new_event)
        db.commit()
    except Exception as e:
        print(f"Error guardando evento: {e}")
        db.rollback()
    finally:
        db.close()


@router.post("/event")
@router.post("/event/")
@router.post("/")
@router.post("")
def receive_alert_event(req: AlertEventRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Buscar usuario admin maestro para asignar el hilo
    admin_user = crud.get_user_by_username(db, "admin")
    user_id = admin_user.id if admin_user else 1

    module_clean = (req.module_name or "Jetson-CV-Node").strip()
    target_title = f"🚨 [EVIDENCIA] {module_clean}"
    
    # Reutilizar el hilo existente del módulo "ojos" o crear uno nuevo si fue borrado
    thread = db.query(models.ChatThread).filter(
        models.ChatThread.title.ilike(f"%{module_clean}%")
    ).order_by(models.ChatThread.id.desc()).first()

    if not thread:
        thread = crud.create_thread(db, user_id=user_id, title=target_title)
    else:
        thread.created_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(thread)
    
    HardwareState.last_alert_thread_id = thread.id

    timestamp_str = datetime.datetime.now().strftime("%H:%M:%S")
    evidence_text = f"⚠️ ALERTA DE EVIDENCIA DESDE MÓDULO JETSON [{timestamp_str}]:\n• Dispositivo: {module_clean}\n• Evento: {req.event}\n• Confianza CV: {int((req.confidence or 0.9)*100)}%"
    crud.add_message(db, thread.id, role="system", content=evidence_text)

    # Reacción Rápida Determinista: Sirena si confidence >= 0.70
    siren_response = None
    conf = req.confidence if req.confidence is not None else 0.9
    if req.auto_siren and conf >= 0.70:
        siren_response = execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
        crud.add_message(db, thread.id, role="system", content="🔊 Respuesta física iniciada: Sirena activada por 30s.")

    # Disparar background task para memoria táctica
    background_tasks.add_task(save_event_and_embedding, module_clean, req.event, conf)

    return {
        "status": "success",
        "thread_id": thread.id,
        "evidence_log": evidence_text,
        "siren_result": siren_response
    }
