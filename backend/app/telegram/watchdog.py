import time
import datetime
import logging
import threading
from typing import Any, Dict, Optional

from . import service as telegram_service
from ..adapters.composition import state
from ..database import SessionLocal
from ..models import models

logger = logging.getLogger("sari_watchdog")

_watchdog_active = False
_watchdog_thread: Optional[threading.Thread] = None

HEARTBEAT_TIMEOUT_SECONDS = 15.0

# Last known liveness per node, kept in this process so the watchdog still detects a silent node
# (and does not mistake a live one for sabotage) while the state store is unavailable.
_last_known: Dict[str, Dict[str, Any]] = {}
_last_known_lock = threading.Lock()


def note_heartbeat(node_id: str, at: Optional[float] = None) -> None:
    """Records in memory that a node reported (called before any store write)."""
    with _last_known_lock:
        _last_known[node_id] = {"last_seen": time.time() if at is None else at, "is_online": True}


def _remember(nodes: Dict[str, Dict[str, Any]]) -> None:
    """A reachable store is authoritative (removed nodes are forgotten); a newer in-memory heartbeat wins."""
    with _last_known_lock:
        fresh = {}
        for nid, node in nodes.items():
            known = _last_known.get(nid)
            last_seen = node.get("last_seen") or 0
            if known is not None and known["last_seen"] > last_seen:
                fresh[nid] = known
            else:
                fresh[nid] = {"last_seen": last_seen, "is_online": bool(node.get("is_online", False))}
        _last_known.clear()
        _last_known.update(fresh)


def _nodes_to_check() -> Dict[str, Dict[str, Any]]:
    """The store's view refreshed into memory; the memory copy alone when the store is down."""
    try:
        _remember(state.list_nodes())
    except Exception as e:
        logger.warning("[WATCHDOG] State store unavailable (%s); supervising from the in-memory copy.", e)
    with _last_known_lock:
        return {nid: dict(node) for nid, node in _last_known.items()}


def _mark_offline(node_id: str) -> None:
    with _last_known_lock:
        if node_id in _last_known:
            _last_known[node_id]["is_online"] = False
    try:
        state.merge_node(node_id, {"is_online": False})
    except Exception as e:
        logger.warning("[WATCHDOG] Could not mark %s offline in the store: %s", node_id, e)

def reset_node_connection_state(node_id: str):
    """Resets the debouncing flag when a node sends telemetry and is active.

    The flag lives in the StateRepository, so the debounce holds across processes and restarts.
    """
    try:
        if state.clear_disconnect_notified(node_id):
            logger.info(f"[WATCHDOG] Node {node_id} reconnected. Disconnection alert debouncer reset.")
    except Exception as e:
        logger.warning("[WATCHDOG] Could not reset the disconnection debounce for %s: %s", node_id, e)

def trigger_node_disconnection_alert(node_id: str, reason: str = "Desconexión abrupta") -> bool:
    """Triggers a critical anti-tamper alert to Telegram when a node drops connection."""
    try:
        first = state.mark_disconnect_notified(node_id)
    except Exception as e:
        # Fail open: a possible sabotage alert is worth a duplicate when the store is unavailable.
        logger.warning("[WATCHDOG] Debounce store unavailable for %s (%s); alerting anyway.", node_id, e)
        first = True
    if not first:
        logger.debug(f"[WATCHDOG] Disconnection for {node_id} already notified; debounced.")
        return False

    try:
        node_data = state.get_node(node_id) or {}
    except Exception:
        node_data = {}
    name = node_data.get("name", f"Módulo ({node_id})")
    ip = node_data.get("ip", "Desconocida")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

    # Add error log to SOC audit
    try:
        state.add_log(
            f"🚨 POSIBLE SABOTAJE PERIMETRAL: Pérdida total de señal con [{node_id}] ({reason})",
            level="ERROR",
            camera_module=node_id
        )
    except Exception as e:
        logger.warning("[WATCHDOG] Could not write the sabotage log entry for %s: %s", node_id, e)

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

    # Send alert as pure text with tactical inline action buttons (no photo/capture)
    return telegram_service.send_telegram_message(alert_text, reply_markup=reply_markup)

def _watchdog_worker():
    global _watchdog_active
    logger.info("[WATCHDOG] Anti-tamper connection monitor worker started.")

    while _watchdog_active:
        try:
            now = time.time()
            for nid, node in _nodes_to_check().items():
                last_seen = node.get("last_seen") or 0
                # If node was considered online but has been silent for >15s without LWT:
                if node.get("is_online") and (now - last_seen > HEARTBEAT_TIMEOUT_SECONDS):
                    logger.warning(f"[WATCHDOG] Heartbeat timeout for node {nid} ({now - last_seen:.1f}s silent).")
                    _mark_offline(nid)
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
