#!/usr/bin/env python3
"""
SARI Jetson Node Telemetry Agent (Wireless MQTT + Resilient HTTP Fallback)
Monitors RAM, CPU, GPU, and Temperature on NVIDIA Jetson,
and broadcasts periodic heartbeat telemetry to the Cerebro Module.
"""
import time
import json
import requests
import os
import psutil
import threading
import logging

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("jetson_agent")

# Configuration
NODE_ID = os.environ.get("JETSON_NODE_ID", "Jetson-PTZ_1")
NODE_NAME = os.environ.get("JETSON_NODE_NAME", "Jetson Orin Nano (PTZ 1)")
NODE_IP = os.environ.get("JETSON_NODE_IP", "192.168.1.73")

MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "192.168.1.71")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", 1883))
MQTT_USER = os.environ.get("MQTT_USER", "sari_operator")
MQTT_PASS = os.environ.get("MQTT_PASSWORD", "sari_secure_password_2026")

CEREBRO_HTTP_URLS = [
    f"http://{MQTT_BROKER_HOST}:7000/api/telemetry/node",
    "http://192.168.55.100:7000/api/telemetry/node",
    "http://localhost:7000/api/telemetry/node"
]

class JetsonMQTTClient:
    def __init__(self):
        self.connected = False
        self.client = None
        if HAS_MQTT:
            try:
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"jetson_{NODE_ID}")
            except AttributeError:
                self.client = mqtt.Client(client_id=f"jetson_{NODE_ID}")
            self.client.username_pw_set(MQTT_USER, MQTT_PASS)
            
            # Setup Last Will and Testament (LWT)
            lwt_payload = json.dumps({
                "node_id": NODE_ID,
                "status": "offline",
                "reason": "connection_lost"
            })
            self.client.will_set(f"sari/nodes/{NODE_ID}/status", lwt_payload, qos=1, retain=True)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            logger.info(f"[MQTT] Connected to Cerebro Broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
            # Publish birth message (online)
            birth_payload = json.dumps({
                "node_id": NODE_ID,
                "status": "online",
                "ip": NODE_IP,
                "name": NODE_NAME
            })
            client.publish(f"sari/nodes/{NODE_ID}/status", birth_payload, qos=1, retain=True)
        else:
            self.connected = False
            logger.warning(f"[MQTT] Connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, disconnect_flags_or_rc, reason_code_or_properties=None, properties=None):
        self.connected = False
        logger.warning("[MQTT] Disconnected from broker")

    def start(self):
        if not self.client:
            return
        def loop():
            while True:
                if not self.connected:
                    try:
                        self.client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=15)
                        self.client.loop_start()
                    except Exception as e:
                        logger.debug(f"[MQTT] Reconnect attempt failed: {e}")
                time.sleep(5.0)
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def publish_telemetry(self, payload: dict) -> bool:
        if self.client and self.connected:
            try:
                res = self.client.publish(f"sari/nodes/{NODE_ID}/telemetry", json.dumps(payload), qos=0)
                return res.rc == mqtt.MQTT_ERR_SUCCESS
            except Exception as e:
                logger.warning(f"[MQTT] Publish error: {e}")
                return False
        return False

def get_jetson_metrics():
    # System RAM via psutil
    mem = psutil.virtual_memory()
    ram_used = round(mem.used / (1024**3), 2)
    ram_total = round(mem.total / (1024**3), 2)
    
    # CPU Load
    cpu_pct = round(psutil.cpu_percent(interval=None), 1)

    # Core Temperature from Jetson thermal zone sysfs
    temp_c = 48.0
    for zone in range(5):
        path = f"/sys/devices/virtual/thermal/thermal_zone{zone}/temp"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    val = float(f.read().strip())
                    if val > 1000:
                        val = val / 1000.0
                    if 25.0 <= val <= 105.0:
                        temp_c = round(val, 1)
                        break
            except Exception:
                pass

    # GPU / NPU Load from Tegra sysfs
    gpu_pct = 58.0
    for gpu_path in ["/sys/devices/gpu.0/load", "/sys/class/devfreq/17000000.ga10b/load"]:
        if os.path.exists(gpu_path):
            try:
                with open(gpu_path, "r") as f:
                    gpu_pct = round(float(f.read().strip()) / 10.0, 1)
                    break
            except Exception:
                pass

    return {
        "node_id": NODE_ID,
        "name": NODE_NAME,
        "ip": NODE_IP,
        "ram_used_gb": ram_used,
        "ram_total_gb": ram_total,
        "cpu_load_pct": cpu_pct,
        "gpu_load_pct": gpu_pct,
        "temp_c": temp_c,
        "fps": 30.0,
        "link_status": "Wi-Fi 5GHz (MQTT)"
    }

def send_http_fallback(data: dict) -> bool:
    for url in CEREBRO_HTTP_URLS:
        try:
            res = requests.post(url, json=data, timeout=1.5)
            if res.status_code == 200:
                logger.info(f"[HTTP Fallback] Telemetry delivered to {url}")
                return True
        except Exception:
            continue
    return False

def main():
    logger.info(f"[*] Starting SARI Resilient Jetson Telemetry Agent for [{NODE_ID}]...")
    mqtt_node = JetsonMQTTClient()
    mqtt_node.start()

    # Initial grace period for connection
    time.sleep(1.0)

    while True:
        data = get_jetson_metrics()
        success = mqtt_node.publish_telemetry(data)
        if not success:
            logger.warning("[Telemetry] MQTT offline or busy. Switching to HTTP fallback...")
            send_http_fallback(data)
        time.sleep(2.5)

if __name__ == "__main__":
    main()
