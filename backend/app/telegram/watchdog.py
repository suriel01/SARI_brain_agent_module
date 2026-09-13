import time
import datetime
import logging
import threading
from typing import Dict, Any, Set, Optional

from .service import send_telegram_alert_photo, send_telegram_message, get_default_chat_id
from ..routers.hardware import HardwareState
from ..database import SessionLocal
from ..models import models

logger = logging.getLogger("sari_watchdog")

_disconnected_nodes_notified: Set[str] = set()
_watchdog_active = False
_watchdog_thread: Optional[threading.Thread] = None

def reset_node_connection_state(node_id: str):
    """Resets the debouncing flag when a node sends telemetry and is active."""
    if node_id in _disconnected_nodes_notified:
        _disconnected_nodes_notified.remove(node_id)
        logger.info(f"[WATCHDOG] Node {node_id} reconnected. Disconnection alert debouncer reset.")

def trigger_node_disconnection_alert(node_id: str, reason: str = "Desconexión abrupta") -> bool:
    """Triggers a critical anti-tamper alert to Telegram when a node drops connection."""
    global _disconnected_nodes_notified

    if node_id in _disconnected_nodes_notified:
        logger.debug(f"[WATCHDOG] Disconnection for {node_id} already notified; debounced.")
        return False

    _disconnected_nodes_notified.add(node_id)

    node_data = HardwareState.nodes.get(node_id, {})
    name = node_data.get("name", f"Módulo ({node_id})")
    ip = node_data.get("ip", "Desconocida")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

    # Add error log to SOC audit
    HardwareState.add_log(
        f"🚨 POSIBLE SABOTAJE PERIMETRAL: Pérdida total de señal con [{node_id}] ({reason})",
        level="ERROR",
        camera_module=node_id
    )

    alert_text = (
        f"🚨 *ALERTA CRÍTICA: POSIBLE SABOTAJE / INTRUSIÓN* 🚨\n\n"
        f"⚠️ *Se ha perdido repentinamente la comunicación con el módulo:*\n"
        f"• *Dispositivo:* `{node_id}` ({name})\n"
        f"• *Dirección IP:* `{ip}`\n"
        f"• *Causa Detectada:* `{reason}`\n"
        f"• *Marca Temporal:* `{now_str}`\n\n"
        f"🛡️ *Protocolo de Seguridad:* Verifique el perímetro físico de inmediato o active la respuesta táctica preventiva."
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🚨 Activar Sirena 30s", "callback_data": "btn_siren_activate"},
                {"text": "🔒 Bloquear Accesos", "callback_data": "btn_gates_lock"}
            ],
            [
                {"text": "🔊 Silenciar Sirena", "callback_data": "btn_siren_silence"}
            ]
        ]
    }

    # Fetch last known evidence snapshot from DB for this camera or overall
    snapshot = None
    db = SessionLocal()
    try:
        last_evidence = db.query(models.ChatMessage).filter(
            models.ChatMessage.snapshot.isnot(None)
        ).order_by(models.ChatMessage.id.desc()).first()
        if last_evidence and last_evidence.snapshot:
            snapshot = last_evidence.snapshot
    except Exception as e:
        logger.warning(f"[WATCHDOG] Error querying last evidence: {e}")
    finally:
        db.close()

    if snapshot:
        return send_telegram_alert_photo(
            photo_base64_or_bytes=snapshot,
            caption=alert_text,
            reply_markup=reply_markup
        )
    else:
        return send_telegram_message(alert_text, reply_markup=reply_markup)

def _watchdog_worker():
    global _watchdog_active
    logger.info("[WATCHDOG] Anti-tamper connection monitor worker started.")

    while _watchdog_active:
        try:
            now = time.time()
            for nid, node in list(HardwareState.nodes.items()):
                last_seen = node.get("last_seen", 0)
                is_online = node.get("is_online", False)

                # If node was considered online but has been silent for >15s without LWT:
                if is_online and (now - last_seen > 15.0):
                    logger.warning(f"[WATCHDOG] Heartbeat timeout for node {nid} ({now - last_seen:.1f}s silent).")
                    node["is_online"] = False
                    trigger_node_disconnection_alert(nid, reason="Pérdida de señal / Heartbeat timeout > 15s")

            time.sleep(4.0)
        except Exception as e:
            logger.debug(f"[WATCHDOG] Watchdog worker exception: {e}")
            time.sleep(4.0)

def start_watchdog():
    global _watchdog_active, _watchdog_thread
    if _watchdog_active:
        return
    _watchdog_active = True
    _watchdog_thread = threading.Thread(target=_watchdog_worker, daemon=True)
    _watchdog_thread.start()
    logger.info("[WATCHDOG] Anti-tamper Watchdog Service active.")

def stop_watchdog():
    global _watchdog_active
    _watchdog_active = False
    logger.info("[WATCHDOG] Watchdog Service stopped.")
