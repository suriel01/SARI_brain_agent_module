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
OLLAMA_EMBED_MODEL = "nomic-embed-text"

class AlertEventRequest(BaseModel):
    module_name: Optional[str] = "Jetson-PTZ_1"
    camara_id: Optional[str] = "PTZ_1"
    event_type: str = "intrusion"
    severity: str = "high"
    message: str = "Intrusión detectada"
    confidence: Optional[float] = None
    duration: Optional[float] = None
    snapshot: Optional[str] = None
    image_base64: Optional[str] = None
    metadata: Optional[dict] = {}

from ..models import models
from ..ws import manager

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


import time

@router.get("/event")
@router.get("/event/")
@router.get("/")
def get_alerts_status_and_logs(db: Session = Depends(get_db)):
    """Endpoint GET para consultar el estado del receptor de alertas y ver el historial de detecciones."""
    db_events = db.query(models.EventLog).order_by(models.EventLog.timestamp.desc()).limit(20).all()
    events_list = [
        {
            "id": ev.id,
            "timestamp": ev.timestamp.strftime("%Y-%m-%d %H:%M:%S") if ev.timestamp else None,
            "module_name": ev.module_name,
            "event_description": ev.event_description,
            "confidence": ev.confidence
        }
        for ev in db_events
    ]
    return {
        "status": "online",
        "endpoint": "POST /api/alerts/event",
        "info": "El receptor de alertas SARI está activo. Para registrar una intrusión, envíe un HTTP POST con el payload JSON de la Jetson.",
        "recent_detections_count": len(events_list),
        "recent_detections": events_list
    }


@router.post("/event")
@router.post("/event/")
@router.post("/alerts/event")
@router.post("/alerts/event/")
@router.post("/alert/event")
@router.post("/alert/event/")
@router.post("/alerta")
@router.post("/alertas")
@router.post("/")
def receive_alert_event(req: AlertEventRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    admin_user = crud.get_user_by_username(db, "admin")
    user_id = admin_user.id if admin_user else 1

    module_clean = req.camara_id or req.module_name or "Jetson-PTZ_1"
    target_title = f"🚨 [EVIDENCIA] {module_clean}"
    
    # Reutilizar o crear hilo
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
    
    # Resolver nivel de confianza
    conf = req.confidence
    if conf is None and req.metadata:
        conf = float(req.metadata.get("confidence", 0.90))
    if conf is None:
        conf = 0.90

    # Normalizar snapshot fotográfico en formato Data URL Base64
    final_snapshot = req.snapshot
    if not final_snapshot and req.image_base64:
        if req.image_base64.startswith("data:image"):
            final_snapshot = req.image_base64
        else:
            final_snapshot = f"data:image/jpeg;base64,{req.image_base64}"
    elif final_snapshot and not final_snapshot.startswith("data:image"):
        final_snapshot = f"data:image/jpeg;base64,{final_snapshot}"

    evidence_text = f"⚠️ ALERTA DE EVIDENCIA DESDE MÓDULO JETSON [{timestamp_str}]:\n• Dispositivo: {module_clean}\n• Tipo: {req.event_type} ({req.severity})\n• Evento: {req.message}\n• Confianza CV: {int(conf*100)}%"
    
    # Guardar mensaje con captura fotográfica
    crud.add_message(db, thread.id, role="system", content=evidence_text, snapshot=final_snapshot)

    # Registrar inmediatamente en los logs de auditoría del SOC (Hardware Control)
    log_level = "ERROR" if req.severity == "high" or req.event_type == "intrusion" else "WARN" if req.severity == "medium" else "INFO"
    HardwareState.add_log(
        msg=f"🚨 [{module_clean}] {req.message} (Conf: {int(conf*100)}%)",
        level=log_level,
        camera_module="JETSON_CV"
    )

    siren_response = None
    if req.event_type == "intrusion" and conf >= 0.70:
        HardwareState.siren_active = True
        HardwareState.alert_count += 1
        HardwareState.last_alert_time = time.time()
        
        siren_response = execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
        crud.add_message(db, thread.id, role="system", content="🔊 Respuesta física iniciada: Sirena activada por 30s mediante orden automática.")
        
        # Broadcast the siren state to React via Websocket
        background_tasks.add_task(manager.broadcast_json, {
            "event": "siren_activated",
            "camara_id": module_clean,
            "severity": req.severity,
            "thread_id": thread.id,
            "snapshot": final_snapshot
        })

    # Tarea en segundo plano para guardar vector de memoria
    background_tasks.add_task(save_event_and_embedding, module_clean, req.message, conf)

    return {
        "status": "success",
        "thread_id": thread.id,
        "evidence_log": evidence_text,
        "siren_result": siren_response,
        "has_snapshot": bool(final_snapshot)
    }


