import os
import time
import logging
import threading
import paho.mqtt.client as mqtt
from .handlers import LEGACY_ALERT_TOPIC, route_message

logger = logging.getLogger("sari_mqtt")

from ..config import get_settings

_settings = get_settings()
BROKER_HOST = _settings.mqtt_host
BROKER_PORT = _settings.mqtt_port
BROKER_USER = _settings.mqtt_user
BROKER_PASS = _settings.mqtt_password

_mqtt_client = None


def subscriptions(legacy_alerts: bool) -> list:
    """Topics the brain listens to. Per-node alert topics are authenticated by the broker ACL."""
    topics = [
        ("sari/nodes/+/telemetry", 0),
        ("sari/nodes/+/status", 1),
        ("sari/nodes/+/alerts", 1),
    ]
    if legacy_alerts:
        topics.append((LEGACY_ALERT_TOPIC, 1))
    return topics

def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f"[MQTT] Connected successfully to broker at {BROKER_HOST}:{BROKER_PORT}")
        topics = subscriptions(_settings.mqtt_legacy_alerts)
        client.subscribe(topics)
        logger.info("[MQTT] Subscribed to %s", ", ".join(t for t, _ in topics))
    else:
        logger.error(f"[MQTT] Failed to connect to broker, return code: {rc}")

def _on_disconnect(client, userdata, disconnect_flags_or_rc, reason_code_or_properties=None, properties=None):
    logger.warning("[MQTT] Disconnected from broker. Auto-reconnection active in loop_start.")

def _on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload_str = msg.payload.decode("utf-8")
    except Exception:
        payload_str = str(msg.payload)

    route_message(topic, payload_str, legacy_alerts=_settings.mqtt_legacy_alerts)

def start_mqtt_client():
    """Starts the background MQTT listener thread."""
    global _mqtt_client
    if _mqtt_client is not None:
        return _mqtt_client

    if _settings.mqtt_legacy_alerts:
        logger.warning(
            "[MQTT] SARI_MQTT_LEGACY_ALERTS is on: alerts on %s are accepted without proof of which node sent them. "
            "Disable it once every node publishes to sari/nodes/<node>/alerts.", LEGACY_ALERT_TOPIC)

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sari_brain_consumer")
    except AttributeError:
        client = mqtt.Client(client_id="sari_brain_consumer")

    client.username_pw_set(BROKER_USER, BROKER_PASS)
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

    def _connect_worker():
        connected = False
        while not connected:
            try:
                logger.info(f"[MQTT] Attempting connection to {BROKER_HOST}:{BROKER_PORT}...")
                client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
                client.loop_start()
                connected = True
                logger.info("[MQTT] Client loop started.")
            except Exception as e:
                logger.warning(f"[MQTT] Connection failed ({e}). Retrying in 4s...")
                time.sleep(4.0)

    t = threading.Thread(target=_connect_worker, daemon=True)
    t.start()
    _mqtt_client = client
    return _mqtt_client

def get_mqtt_client():
    global _mqtt_client
    return _mqtt_client

def stop_mqtt_client():
    global _mqtt_client
    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
            logger.info("[MQTT] Client stopped.")
        except Exception as e:
            logger.error(f"[MQTT] Error stopping client: {e}")
        _mqtt_client = None
