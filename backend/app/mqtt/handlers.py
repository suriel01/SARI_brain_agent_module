import json
import logging
import time

from ..database import SessionLocal
from ..routers.hardware import HardwareState
from ..services.alert_ingest import ingest_alert, normalize_snapshot
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
    """Handles critical intrusion alerts from sari/alerts with Base64 snapshot.

    The siren actor is the node named in the payload; broker-level node authentication is T11.
    """
    db = SessionLocal()
    try:
        data = json.loads(payload_str)
        result = ingest_alert(
            db,
            node_id=data.get("camara_id") or data.get("module_name") or "Jetson-PTZ_1",
            module=data.get("camara_id") or data.get("module_name") or "Jetson-PTZ_1",
            event_type=data.get("event_type", "intrusion"),
            severity=data.get("severity", "high"),
            message=data.get("message", "Intrusión detectada"),
            confidence=float(data.get("confidence", 0.90)),
            snapshot=normalize_snapshot(data.get("snapshot") or data.get("image_base64")),
            node_ip=data.get("ip", "192.168.1.73"),
            transport_label=" (MQTT)",
            store_embedding=False,
        )
        logger.info(f"[MQTT] Alert successfully ingested and persisted for thread {result.thread_id}")
    except Exception as e:
        logger.error(f"[MQTT] Error handling alert event: {e}")
        db.rollback()
    finally:
        db.close()
