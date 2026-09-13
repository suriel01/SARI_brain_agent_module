# Prompt para el Agente del Módulo Jetson Orin Nano

Copia y pega las siguientes instrucciones al agente de la Jetson para configurar la telemetría inalámbrica MQTT y el envío de alertas con evidencia:

---

```markdown
Hola Agente Jetson. El Módulo Cerebro SARI ha habilitado el Broker MQTT Mosquitto en la red Wi-Fi en la IP `192.168.1.71` (puerto 1883) con autenticación segura y soporte para Last Will and Testament (LWT).

Debes configurar la Jetson para que transmita telemetría en tiempo real por Wi-Fi de forma persistente y envíe alertas de detección YOLO directamente al broker MQTT.

### Paso 1: Instalar dependencias
Ejecuta:
```bash
pip3 install --upgrade paho-mqtt psutil requests
```

### Paso 2: Crear el script de telemetría dual (/home/jetson/jetson_telemetry.py)
Crea o sobrescribe el archivo `/home/jetson/jetson_telemetry.py` con el siguiente contenido:

```python
#!/usr/bin/env python3
"""
SARI Jetson Node Telemetry Agent (Wireless MQTT + Resilient HTTP Fallback)
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

NODE_ID = os.environ.get("JETSON_NODE_ID", "Jetson-PTZ_1")
NODE_NAME = os.environ.get("JETSON_NODE_NAME", "Jetson Orin Nano (PTZ 1)")
NODE_IP = os.environ.get("JETSON_NODE_IP", "192.168.1.73")

MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "192.168.1.71")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", 1883))
MQTT_USER = os.environ.get("MQTT_USER", "sari_operator")
MQTT_PASS = os.environ.get("MQTT_PASSWORD", "sari_secure_password_2026")

CEREBRO_HTTP_URLS = [
    f"http://{MQTT_BROKER_HOST}:7000/api/telemetry/node",
    "http://192.168.55.100:7000/api/telemetry/node"
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
            
            # Last Will and Testament (LWT)
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
            logger.info(f"[MQTT] Conectado exitosamente al Cerebro en {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
            birth_payload = json.dumps({
                "node_id": NODE_ID,
                "status": "online",
                "ip": NODE_IP,
                "name": NODE_NAME
            })
            client.publish(f"sari/nodes/{NODE_ID}/status", birth_payload, qos=1, retain=True)
        else:
            self.connected = False
            logger.warning(f"[MQTT] Error de conexion, codigo: {rc}")

    def _on_disconnect(self, client, userdata, disconnect_flags_or_rc, reason_code_or_properties=None, properties=None):
        self.connected = False
        logger.warning("[MQTT] Desconectado del broker MQTT")

    def start(self):
        if not self.client:
            return
        def loop():
            while True:
                if not self.connected:
                    try:
                        self.client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=15)
                        self.client.loop_start()
                    except Exception:
                        pass
                time.sleep(5.0)
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def publish_telemetry(self, payload: dict) -> bool:
        if self.client and self.connected:
            try:
                res = self.client.publish(f"sari/nodes/{NODE_ID}/telemetry", json.dumps(payload), qos=0)
                return res.rc == mqtt.MQTT_ERR_SUCCESS
            except Exception:
                return False
        return False

def get_jetson_metrics():
    mem = psutil.virtual_memory()
    ram_used = round(mem.used / (1024**3), 2)
    ram_total = round(mem.total / (1024**3), 2)
    cpu_pct = round(psutil.cpu_percent(interval=None), 1)

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

    gpu_pct = 55.0
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
                logger.info(f"[HTTP Fallback] Telemetria enviada a {url}")
                return True
        except Exception:
            continue
    return False

def main():
    logger.info(f"[*] Iniciando Agente de Telemetria SARI para [{NODE_ID}]...")
    mqtt_node = JetsonMQTTClient()
    mqtt_node.start()
    time.sleep(1.0)

    while True:
        data = get_jetson_metrics()
        success = mqtt_node.publish_telemetry(data)
        if not success:
            logger.warning("[Telemetry] MQTT no disponible. Aplicando fallback HTTP...")
            send_http_fallback(data)
        time.sleep(2.5)

if __name__ == "__main__":
    main()
```

### Paso 3: Configurar servicio systemd persistente
Crea el archivo `/etc/systemd/system/sari-jetson.service`:

```ini
[Unit]
Description=SARI Jetson Telemetry & Heartbeat Daemon (MQTT Wireless + HTTP Fallback)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/jetson
Environment="PYTHONUNBUFFERED=1"
Environment="MQTT_BROKER_HOST=192.168.1.71"
Environment="MQTT_BROKER_PORT=1883"
Environment="MQTT_USER=sari_operator"
Environment="MQTT_PASSWORD=sari_secure_password_2026"
Environment="JETSON_NODE_ID=Jetson-PTZ_1"
Environment="JETSON_NODE_NAME=Jetson Orin Nano (PTZ 1)"
Environment="JETSON_NODE_IP=192.168.1.73"

ExecStart=/usr/bin/python3 /home/jetson/jetson_telemetry.py

Restart=always
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Activa e inicia el servicio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sari-jetson.service
sudo systemctl status sari-jetson.service
```

### Paso 4: Enviar Alertas YOLO con Snapshot vía MQTT
En el script de detección YOLO (`camara_ptz.py`), cuando se detecte una intrusión (`person` con confianza > 0.70), publica el JSON al broker MQTT al topic `sari/alerts` con QoS 1:

```python
import paho.mqtt.publish as publish
import json

alert_payload = {
    "camara_id": "Jetson-PTZ_1",
    "event_type": "intrusion",
    "confidence": round(confidence, 2),
    "message": f"Intrusion detectada en zona perimetral: {label}",
    "severity": "high",
    "snapshot": snapshot_base64,  # Imagen JPEG codificada en Base64
    "ip": "192.168.1.73"
}

publish.single(
    topic="sari/alerts",
    payload=json.dumps(alert_payload),
    qos=1,
    hostname="192.168.1.71",
    port=1883,
    auth={"username": "sari_operator", "password": "sari_secure_password_2026"},
    keepalive=10
)
```
```
