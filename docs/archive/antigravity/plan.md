# Plan Técnico: Arquitectura de Comunicación Inalámbrica MQTT (Spec 002)

## 1. Estructura de Módulos y Servicios
```
SARI_brain_agent/
├── docker-compose.yml              # Agrega servicio 'sari-mqtt' (Eclipse Mosquitto en puerto 1883)
├── mosquitto/
│   ├── config/
│   │   ├── mosquitto.conf          # Configuración del broker (puerto 1883, allow_anonymous o passwd)
│   │   └── passwd                  # Archivo de contraseñas de Mosquitto
├── backend/
│   ├── requirements.txt            # Agrega 'aiomqtt>=2.0.0' o 'paho-mqtt>=2.0.0'
│   └── app/
│       ├── mqtt/
│       │   ├── __init__.py
│       │   ├── client.py           # Gestor de conexión y suscripción MQTT en segundo plano (asyncio)
│       │   └── handlers.py         # Despacho de mensajes: telemetría -> HardwareState, alertas -> CRUD/DB/WS
│       └── main.py                 # Startup/shutdown hooks para iniciar el listener MQTT en FastAPI
├── tests/
│   ├── test_mqtt_telemetry.py      # Test unitario y de integración para publicación/ingesta MQTT
│   └── test_mqtt_alerts.py         # Test de alerta de intrusión con snapshot por MQTT
└── jetson_telemetry.py             # Script dual en la Jetson (MQTT Primario + Fallback HTTP)
```

## 2. Modelo de Tópicos y Formato de Datos

### 2.1 Tópico: `sari/nodes/{node_id}/status`
* **Propósito**: Conexión y LWT (Last Will and Testament) para detección instantánea de caídas.
* **QoS**: 1 | **Retain**: `True`
* **Payload Conectado**:
  ```json
  {"node_id": "Jetson-PTZ_1", "status": "online", "ip": "192.168.1.73", "timestamp": 1789182300.0}
  ```
* **Payload Desconectado (LWT)**:
  ```json
  {"node_id": "Jetson-PTZ_1", "status": "offline", "timestamp": 1789182350.0}
  ```

### 2.2 Tópico: `sari/nodes/{node_id}/telemetry`
* **Propósito**: Transmisión continua de telemetría de hardware cada 3 segundos.
* **QoS**: 0 | **Retain**: `False`
* **Payload**:
  ```json
  {
    "node_id": "Jetson-PTZ_1",
    "name": "Jetson Orin Nano (PTZ 1)",
    "ip": "192.168.1.73",
    "ram_used_gb": 3.85,
    "ram_total_gb": 7.44,
    "cpu_load_pct": 32.0,
    "gpu_load_pct": 68.0,
    "temp_c": 54.5,
    "fps": 30.0,
    "link_status": "Wi-Fi 5GHz (Stable)"
  }
  ```

### 2.3 Tópico: `sari/alerts`
* **Propósito**: Notificación de intrusiones con foto de evidencia visual.
* **QoS**: 1 | **Retain**: `False`
* **Payload**:
  ```json
  {
    "module_name": "Jetson-PTZ_1",
    "camara_id": "PTZ_1",
    "event_type": "intrusion",
    "severity": "high",
    "message": "Intrusión detectada (persona_mas_de_5s)",
    "confidence": 0.94,
    "duration": 5.2,
    "snapshot": "data:image/jpeg;base64,...",
    "timestamp": 1789182310.0
  }
  ```

---

## 3. Algoritmos de Cálculo y Despacho

### 3.1 Receptor Asíncrono en FastAPI (`app/mqtt/client.py`)
1. Al iniciar la aplicación (`startup_event` o Lifespan), se inicia la tarea `asyncio.create_task(mqtt_listener_loop())`.
2. Se conecta al broker `sari-mqtt:1883` con reconexión automática en bucle infinito exponencial (1s a 30s).
3. Se suscribe a `sari/nodes/+/telemetry`, `sari/nodes/+/status` y `sari/alerts`.
4. Al recibir un mensaje:
   - Valida el tamaño (< 10 MB) y parsea el JSON.
   - Si es telemetría: actualiza `HardwareState.nodes[node_id]`.
   - Si es status: actualiza `HardwareState.nodes[node_id]["is_online"]` y loguea en auditoría.
   - Si es alerta: crea sesión `SessionLocal()`, persiste el mensaje con snapshot en el hilo activo de chat y emite por WebSocket `manager.broadcast()`.

### 3.2 Cliente Resiliente en la Jetson (`jetson_telemetry.py`)
1. Intenta conectar al broker MQTT en `192.168.1.71:1883` configurando el LWT antes del `connect`.
2. Publica status `online` retenido.
3. En el bucle principal (cada 3s):
   - Lee métricas físicas locales de Tegra sysfs y psutil.
   - Si MQTT está conectado, publica en `sari/nodes/{node_id}/telemetry` (QoS 0).
   - Si MQTT reporta desconexión temporal, conmuta de inmediato a HTTP POST `http://192.168.1.71:8000/api/telemetry/node`.

---

## 4. Estrategia de Tests y Validación
1. **Test 1: Broker y Contenedor (`tests/test_mqtt_broker.py`)**:
   - Comprueba que el broker Mosquitto responde en el puerto 1883.
   - Autenticación con credenciales válidas e inválidas.
2. **Test 2: Flujo de Telemetría (`tests/test_mqtt_telemetry.py`)**:
   - Publica paquete de telemetría sintético por MQTT.
   - Consulta `GET /api/hardware/state` vía HTTP y verifica que `HardwareState.nodes` refleja los valores exactos en memoria.
3. **Test 3: Detección LWT (`tests/test_mqtt_lwt.py`)**:
   - Conecta un cliente simulado con LWT, fuerza un cierre abrupto de socket sin desconexión limpia (`socket.close()`).
   - Verifica que el broker publica el LWT y el Cerebro actualiza el estado a `is_online: False`.
4. **Test 4: Alertas e Ingesta con Snapshot (`tests/test_mqtt_alerts.py`)**:
   - Publica alerta en `sari/alerts` con imagen Base64.
   - Verifica que el mensaje se almacena en PostgreSQL y se transmite vía WebSocket.
