import json
import logging
import time
import datetime
from typing import Dict, Any

from ..database import SessionLocal
from ..routers.hardware import HardwareState, execute_physical_tool
from ..crud import crud
from ..models import models
from ..ws import manager
from ..telegram.service import send_telegram_alert_photo
from ..telegram.watchdog import reset_node_connection_state, trigger_node_disconnection_alert

logger = logging.getLogger("sari_mqtt")

def handle_telemetry_message(topic: str, payload_str: str):
    """Handles messages from sari/nodes/{node_id}/telemetry"""
    try:
        data = json.loads(payload_str)
        parts = topic.split("/")
        node_id = data.get("node_id") or (parts[2] if len(parts) >= 3 else "Jetson-PTZ_1")
        
        HardwareState.nodes[node_id] = {
            "node_id": node_id,
            "name": data.get("name", f"Jetson Node ({node_id})"),
            "ip": data.get("ip", "192.168.1.73"),
            "ram_used_gb": data.get("ram_used_gb", 3.8),
            "ram_total_gb": data.get("ram_total_gb", 7.44),
            "cpu_load_pct": data.get("cpu_load_pct", 30.0),
            "gpu_load_pct": data.get("gpu_load_pct", 50.0),
            "temp_c": data.get("temp_c", 50.0),
            "fps": data.get("fps", 30.0),
            "link_status": data.get("link_status", "Wi-Fi (1Gbps)"),
            "last_seen": time.time(),
            "is_online": True
        }
        reset_node_connection_state(node_id)
        logger.info(f"[MQTT] Telemetry updated for node {node_id}")
    except Exception as e:
        logger.error(f"[MQTT] Error handling telemetry: {e}")

def handle_status_message(topic: str, payload_str: str):
    """Handles messages from sari/nodes/{node_id}/status (including LWT)"""
    try:
        data = json.loads(payload_str) if payload_str else {}
        parts = topic.split("/")
        node_id = data.get("node_id") or (parts[2] if len(parts) >= 3 else "Jetson-PTZ_1")
        status = str(data.get("status", "offline")).lower()

        if status == "online":
            if node_id in HardwareState.nodes:
                HardwareState.nodes[node_id]["is_online"] = True
                HardwareState.nodes[node_id]["last_seen"] = time.time()
                if "ip" in data:
                    HardwareState.nodes[node_id]["ip"] = data["ip"]
            else:
                HardwareState.nodes[node_id] = {
                    "node_id": node_id,
                    "name": f"Jetson Node ({node_id})",
                    "ip": data.get("ip", "192.168.1.73"),
                    "last_seen": time.time(),
                    "is_online": True
                }
            reset_node_connection_state(node_id)
            HardwareState.add_log(f"🟢 Jetson Node [{node_id}] connected via Wi-Fi (MQTT)", level="INFO", camera_module=node_id)
            logger.info(f"[MQTT] Node {node_id} status ONLINE")
        else:
            # LWT or explicit offline
            if node_id in HardwareState.nodes:
                HardwareState.nodes[node_id]["is_online"] = False
                HardwareState.nodes[node_id]["last_seen"] = 0.0
            HardwareState.add_log(f"⚠️ Jetson Node [{node_id}] disconnected (LWT signal)", level="WARNING", camera_module=node_id)
            trigger_node_disconnection_alert(node_id, reason="Señal LWT / Desconexión física recibida vía MQTT")
            logger.warning(f"[MQTT] Node {node_id} status OFFLINE (LWT)")
    except Exception as e:
        logger.error(f"[MQTT] Error handling status/LWT: {e}")

def handle_alert_message(payload_str: str):
    """Handles critical intrusion alerts from sari/alerts with Base64 snapshot"""
    db = SessionLocal()
    try:
        data = json.loads(payload_str)
        module_clean = data.get("camara_id") or data.get("module_name") or "Jetson-PTZ_1"
        target_title = f"🚨 [EVIDENCIA] {module_clean}"

        admin_user = crud.get_user_by_username(db, "admin")
        user_id = admin_user.id if admin_user else 1

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
        HardwareState.record_node_activity(module_clean, ip=data.get("ip", "192.168.1.73"))

        try:
            import zoneinfo
            local_now = datetime.datetime.now(zoneinfo.ZoneInfo("America/Mexico_City"))
        except Exception:
            local_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))

        timestamp_str = local_now.strftime("%I:%M:%S %p")
        conf = float(data.get("confidence", 0.90))

        # Snapshot normalization
        final_snapshot = data.get("snapshot") or data.get("image_base64")
        if final_snapshot and not final_snapshot.startswith("data:image"):
            final_snapshot = f"data:image/jpeg;base64,{final_snapshot}"

        event_type = data.get("event_type", "intrusion")
        severity = data.get("severity", "high")
        msg = data.get("message", "Intrusión detectada")

        evidence_text = f"⚠️ ALERTA DE EVIDENCIA DESDE MÓDULO JETSON (MQTT) [{timestamp_str}]:\n• Dispositivo: {module_clean}\n• Tipo: {event_type} ({severity})\n• Evento: {msg}\n• Confianza CV: {int(conf*100)}%"

        crud.add_message(db, thread.id, role="system", content=evidence_text, snapshot=final_snapshot)

        log_level = "ERROR" if severity == "high" or event_type == "intrusion" else "WARN"
        HardwareState.add_log(
            msg=f"🚨 [{module_clean}] {msg} (Conf: {int(conf*100)}%)",
            level=log_level,
            camera_module="JETSON_CV"
        )

        # Telegram Tactical Dispatch
        telegram_caption = (
            f"🚨 *ALERTA CRÍTICA SARI — PERÍMETRO*\n\n"
            f"• *Nodo*: `{module_clean}`\n"
            f"• *Evento*: {msg}\n"
            f"• *Severidad*: `{severity.upper()}`\n"
            f"• *Confianza CV*: `{int(conf*100)}%`\n"
            f"• *Hora*: `{timestamp_str}`"
        )
        telegram_buttons = {
            "inline_keyboard": [
                [
                    {"text": "🚨 Activar Sirena 30s", "callback_data": "btn_siren_activate"},
                    {"text": "🔒 Bloquear Accesos", "callback_data": "btn_gates_lock"}
                ],
                [
                    {"text": "🔊 Silenciar Alarma", "callback_data": "btn_silence"},
                    {"text": "📊 Ver Estado", "callback_data": "btn_status"}
                ]
            ]
        }
        try:
            send_telegram_alert_photo(final_snapshot, caption=telegram_caption, reply_markup=telegram_buttons)
        except Exception as ex_tg:
            logger.warning(f"[MQTT->Telegram] Error delivering alert photo: {ex_tg}")

        if event_type == "intrusion" and conf >= 0.70:
            HardwareState.siren_active = True
            HardwareState.alert_count += 1
            HardwareState.last_alert_time = time.time()
            execute_physical_tool("activar_sirena", {"duracion_segundos": 30})
            crud.add_message(db, thread.id, role="system", content="🔊 Respuesta física iniciada: Sirena activada por 30s mediante orden automática.")

            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(manager.broadcast_json({
                        "event": "siren_activated",
                        "camara_id": module_clean,
                        "severity": severity,
                        "thread_id": thread.id,
                        "snapshot": final_snapshot
                    }))
            except Exception as ex:
                logger.warning(f"[MQTT] Could not broadcast via ws: {ex}")

        logger.info(f"[MQTT] Alert successfully ingested and persisted for thread {thread.id}")
    except Exception as e:
        logger.error(f"[MQTT] Error handling alert event: {e}")
        db.rollback()
    finally:
        db.close()
