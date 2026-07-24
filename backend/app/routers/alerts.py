from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import datetime

from ..database import get_db
from ..crud import crud
from .hardware import execute_physical_tool

router = APIRouter()

class AlertEventRequest(BaseModel):
    module_name: str = "Jetson-CV-Node"
    event: str = "Detección perimetral"
    confidence: Optional[float] = 0.95
    auto_siren: Optional[bool] = True

from ..models import models

@router.post("/event")
def receive_alert_event(req: AlertEventRequest, db: Session = Depends(get_db)):
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
    
    timestamp_str = datetime.datetime.now().strftime("%H:%M:%S")
    evidence_text = f"⚠️ ALERTA DE EVIDENCIA DESDE MÓDULO JETSON [{timestamp_str}]:\n• Dispositivo: {module_clean}\n• Evento: {req.event}\n• Confianza CV: {int((req.confidence or 0.9)*100)}%"
    crud.add_message(db, thread.id, role="system", content=evidence_text)

    siren_response = None
    if req.auto_siren:
        siren_response = execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
        crud.add_message(db, thread.id, role="system", content="🔊 Respuesta física iniciada: Sirena activada por 30s.")

    return {
        "status": "success",
        "thread_id": thread.id,
        "evidence_log": evidence_text,
        "siren_result": siren_response
    }
