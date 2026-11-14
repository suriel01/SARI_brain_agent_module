import json
import logging
import time
from typing import Optional

from ..config import get_settings
from ..database import SessionLocal
from ..routers.hardware import NODE_TELEMETRY_FIELDS, HardwareState
from ..services.alert_ingest import ingest_alert, normalize_snapshot
from ..telegram.watchdog import reset_node_connection_state, trigger_node_disconnection_alert

logger = logging.getLogger("sari_mqtt")

def handle_telemetry_message(topic: str, payload_str: str):
    """Handles messages from sari/nodes/{node_id}/telemetry"""
    try:
        data = json.loads(payload_str)
        parts = topic.split("/")
        topic_node = parts[2] if len(parts) >= 4 and parts[0] == "sari" and parts[1] == "nodes" else None
        if not topic_node:
            logger.warning(f"[MQTT] Ignoring message on unexpected topic {topic}")
            return
        payload_node = data.get("node_id")
        if payload_node and payload_node != topic_node:
            logger.warning(f"[MQTT] Ignoring {topic}: payload node_id does not match the topic node")
            return
        node_id = topic_node
        
        HardwareState.nodes[node_id] = {
            "node_id": node_id,
            "name": data.get("name", f"Jetson Node ({node_id})"),
            "ip": data.get("ip"),
            **{field: data.get(field) for field in NODE_TELEMETRY_FIELDS},
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
        topic_node = parts[2] if len(parts) >= 4 and parts[0] == "sari" and parts[1] == "nodes" else None
        if not topic_node:
            logger.warning(f"[MQTT] Ignoring message on unexpected topic {topic}")
            return
        payload_node = data.get("node_id")
        if payload_node and payload_node != topic_node:
            logger.warning(f"[MQTT] Ignoring {topic}: payload node_id does not match the topic node")
            return
        node_id = topic_node
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
                    "ip": data.get("ip"),
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

LEGACY_ALERT_TOPIC = "sari/alerts"


def node_id_from_topic(topic: str, kind: str) -> Optional[str]:
    """Returns the node id of ``sari/nodes/<id>/<kind>`` or None when the topic has another shape."""
    parts = topic.split("/")
    if len(parts) != 4 or parts[0] != "sari" or parts[1] != "nodes" or parts[3] != kind:
        return None
    node_id = parts[2]
    if not node_id or node_id in {"+", "#"}:
        return None
    return node_id


def route_message(topic: str, payload_str: str, legacy_alerts: Optional[bool] = None) -> None:
    """Single MQTT entry point.

    Alerts on ``sari/nodes/<id>/alerts`` are bound to ``<id>``: the broker ACL only lets user ``<id>``
    publish there, so the topic (not the payload) identifies the node. The shared ``sari/alerts``
    topic is accepted only while ``SARI_MQTT_LEGACY_ALERTS`` is on.
    """
    if legacy_alerts is None:
        legacy_alerts = get_settings().mqtt_legacy_alerts

    alert_node = node_id_from_topic(topic, "alerts")
    if alert_node is not None:
        handle_alert_message(payload_str, node_id=alert_node)
    elif topic == LEGACY_ALERT_TOPIC:
        if legacy_alerts:
            handle_alert_message(payload_str)
        else:
            logger.warning("[MQTT] Ignored alert on legacy topic %s (SARI_MQTT_LEGACY_ALERTS is off)", topic)
    elif topic.endswith("/alerts"):
        logger.warning("[MQTT] Ignored alert on malformed topic %s", topic)
    elif "/telemetry" in topic:
        handle_telemetry_message(topic, payload_str)
    elif "/status" in topic:
        handle_status_message(topic, payload_str)
    else:
        logger.info(f"[MQTT] Message received on unhandled topic: {topic}")


def handle_alert_message(payload_str: str, node_id: Optional[str] = None):
    """Handles intrusion alerts (Base64 snapshot included).

    ``node_id`` comes from the per-node topic and is the siren actor. Without it (legacy
    ``sari/alerts``) the actor is the node named in the payload, which the broker cannot verify.
    """
    db = SessionLocal()
    try:
        data = json.loads(payload_str)
        claimed = data.get("camara_id") or data.get("module_name")
        result = ingest_alert(
            db,
            node_id=node_id or claimed or "Jetson-PTZ_1",
            module=claimed or node_id or "Jetson-PTZ_1",
            event_type=data.get("event_type", "intrusion"),
            severity=data.get("severity", "high"),
            message=data.get("message", "Intrusión detectada"),
            confidence=float(data.get("confidence", 0.90)),
            snapshot=normalize_snapshot(data.get("snapshot") or data.get("image_base64")),
            node_ip=data.get("ip"),
            transport_label=" (MQTT)",
            store_embedding=False,
        )
        logger.info(f"[MQTT] Alert successfully ingested and persisted for thread {result.thread_id}")
    except Exception as e:
        logger.error(f"[MQTT] Error handling alert event: {e}")
        db.rollback()
    finally:
        db.close()
