"""Single alert-ingest pipeline shared by the REST (`/api/alerts/event`) and MQTT (`sari/alerts`) transports.

Steps: find or create the evidence thread, store the evidence message, update the in-memory SOC
state and log, dispatch the Telegram alert with its inline keyboard, raise the siren through the
choke point as the node actor, notify the dashboard and optionally store the RAG embedding.
"""
import asyncio
import datetime
import logging
import os
from dataclasses import dataclass
from typing import Optional

import requests
from sqlalchemy.orm import Session

from ..crud import crud
from ..database import SessionLocal
from ..models import models
from ..routers.hardware import Actor, HardwareState, execute_physical_tool
from ..telegram.service import send_telegram_alert_photo
from ..ws import manager

logger = logging.getLogger("sari_alerts")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_EMBED_URL = OLLAMA_URL.replace("/api/chat", "/api/embeddings")
OLLAMA_EMBED_MODEL = "nomic-embed-text"

SIREN_CONFIDENCE_THRESHOLD = 0.70
SIREN_STARTED_MSG = "🔊 Respuesta física iniciada: Sirena activada por 30s mediante orden automática."
SIREN_FAILED_MSG = "❌ Respuesta física fallida: la sirena no pudo activarse ({detail})."

TELEGRAM_ALERT_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "🚨 Activar Sirena 30s", "callback_data": "btn_siren_activate"},
            {"text": "🔒 Bloquear Accesos", "callback_data": "btn_gates_lock"},
        ],
        [
            {"text": "🔊 Silenciar Alarma", "callback_data": "btn_silence"},
            {"text": "📊 Ver Estado", "callback_data": "btn_status"},
        ],
    ]
}


@dataclass
class IngestResult:
    thread_id: int
    evidence_text: str
    siren_result: Optional[dict]
    has_snapshot: bool


def normalize_snapshot(snapshot: Optional[str]) -> Optional[str]:
    """Returns the snapshot as a data URL (raw base64 is assumed to be JPEG)."""
    if not snapshot:
        return None
    return snapshot if snapshot.startswith("data:image") else f"data:image/jpeg;base64,{snapshot}"


def save_event_and_embedding(module_name: str, event_desc: str, confidence: float):
    """Stores the detection in event_logs with its RAG embedding (best effort)."""
    embedding = None
    try:
        res = requests.post(OLLAMA_EMBED_URL, json={"model": OLLAMA_EMBED_MODEL, "prompt": f"[{module_name}] {event_desc}"}, timeout=10.0)
        if res.status_code == 200:
            embedding = res.json().get("embedding")
    except Exception as e:
        logger.warning("Error generating embedding: %s", e)

    db = SessionLocal()
    try:
        db.add(models.EventLog(module_name=module_name, event_description=event_desc, confidence=confidence, embedding=embedding))
        db.commit()
    except Exception as e:
        logger.error("Error storing event: %s", e)
        db.rollback()
    finally:
        db.close()


def _local_time_str() -> str:
    try:
        import zoneinfo

        local_now = datetime.datetime.now(zoneinfo.ZoneInfo("America/Mexico_City"))
    except Exception:
        local_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))
    return local_now.strftime("%I:%M:%S %p")


def _evidence_thread(db: Session, module: str) -> models.ChatThread:
    thread = (
        db.query(models.ChatThread)
        .filter(models.ChatThread.title.ilike(f"%{module}%"))
        .order_by(models.ChatThread.id.desc())
        .first()
    )
    if not thread:
        admin_user = crud.get_user_by_username(db, "admin")
        return crud.create_thread(db, user_id=admin_user.id if admin_user else 1, title=f"🚨 [EVIDENCIA] {module}")
    thread.created_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(thread)
    return thread


def _log_level(event_type: str, severity: str) -> str:
    if severity == "high" or event_type == "intrusion":
        return "ERROR"
    return "WARN" if severity == "medium" else "INFO"


def _broadcast(payload: dict, background_tasks) -> None:
    if background_tasks is not None:
        background_tasks.add_task(manager.broadcast_json, payload)
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast_json(payload))
    except Exception as ex:
        logger.warning("Could not broadcast alert via ws: %s", ex)


def ingest_alert(
    db: Session,
    *,
    node_id: str,
    module: str,
    event_type: str,
    severity: str,
    message: str,
    confidence: float,
    snapshot: Optional[str],
    node_ip: str,
    transport_label: str = "",
    background_tasks=None,
    store_embedding: bool = True,
) -> IngestResult:
    """Runs the alert pipeline. ``node_id`` is the authenticated node the siren actor is bound to."""
    thread = _evidence_thread(db, module)
    HardwareState.last_alert_thread_id = thread.id
    HardwareState.record_node_activity(module, ip=node_ip)

    timestamp_str = _local_time_str()
    conf_pct = int(confidence * 100)
    evidence_text = (
        f"⚠️ ALERTA DE EVIDENCIA DESDE MÓDULO JETSON{transport_label} [{timestamp_str}]:\n"
        f"• Dispositivo: {module}\n• Tipo: {event_type} ({severity})\n• Evento: {message}\n• Confianza CV: {conf_pct}%"
    )
    crud.add_message(db, thread.id, role="system", content=evidence_text, snapshot=snapshot)
    HardwareState.add_log(msg=f"🚨 [{module}] {message} (Conf: {conf_pct}%)", level=_log_level(event_type, severity), camera_module="JETSON_CV")

    caption = (
        f"🚨 *ALERTA CRÍTICA SARI — PERÍMETRO*\n\n"
        f"• *Nodo*: `{module}`\n"
        f"• *Evento*: {message}\n"
        f"• *Severidad*: `{severity.upper()}`\n"
        f"• *Confianza CV*: `{conf_pct}%`\n"
        f"• *Hora*: `{timestamp_str}`"
    )
    try:
        send_telegram_alert_photo(snapshot, caption=caption, reply_markup=TELEGRAM_ALERT_KEYBOARD)
    except Exception as ex_tg:
        logger.warning("Error delivering Telegram alert photo: %s", ex_tg)

    siren_result = None
    if event_type == "intrusion" and confidence >= SIREN_CONFIDENCE_THRESHOLD:
        siren_result = execute_physical_tool("activar_sirena", {"duracion_segundos": 30}, actor=Actor.node(node_id))
        if siren_result.get("status") == "success":
            crud.add_message(db, thread.id, role="system", content=SIREN_STARTED_MSG)
            _broadcast(
                {"event": "siren_activated", "camara_id": module, "severity": severity, "thread_id": thread.id, "snapshot": snapshot},
                background_tasks,
            )
        else:
            crud.add_message(db, thread.id, role="system", content=SIREN_FAILED_MSG.format(detail=siren_result.get("message", "")))

    if store_embedding:
        if background_tasks is not None:
            background_tasks.add_task(save_event_and_embedding, module, message, confidence)
        else:
            save_event_and_embedding(module, message, confidence)

    return IngestResult(thread_id=thread.id, evidence_text=evidence_text, siren_result=siren_result, has_snapshot=bool(snapshot))
