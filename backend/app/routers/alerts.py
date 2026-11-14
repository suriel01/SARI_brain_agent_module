from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..node_auth import require_node
from ..application.alert_ingest import ingest_alert, normalize_snapshot
from .deps import get_current_user

router = APIRouter()

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


@router.get("/event")
@router.get("/event/")
@router.get("/")
def get_alerts_status_and_logs(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
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
def receive_alert_event(req: AlertEventRequest, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db), node_id: str = Depends(require_node)):
    conf = req.confidence
    if conf is None and req.metadata:
        conf = float(req.metadata.get("confidence", 0.90))
    if conf is None:
        conf = 0.90

    result = ingest_alert(
        db,
        node_id=node_id,
        module=req.camara_id or req.module_name or "Jetson-PTZ_1",
        event_type=req.event_type,
        severity=req.severity,
        message=req.message,
        confidence=conf,
        snapshot=normalize_snapshot(req.snapshot or req.image_base64),
        node_ip=request.client.host if request.client else None,
        background_tasks=background_tasks,
    )
    return {
        "status": "success",
        "thread_id": result.thread_id,
        "evidence_log": result.evidence_text,
        "siren_result": result.siren_result,
        "has_snapshot": result.has_snapshot,
    }
