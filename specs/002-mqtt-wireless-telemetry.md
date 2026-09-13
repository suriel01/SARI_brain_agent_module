# Spec 002 — Comunicación Inalámbrica Wi-Fi y Telemetría Robusta vía MQTT

## 1. Contexto
El sistema SARI coordina módulos de percepción perimetral (NVIDIA Jetson Orin Nano con YOLO) y el Módulo Cerebro (FastAPI, Ollama, React Dashboard). Anteriormente, la comunicación de telemetría dependía de polling HTTP directo por cable USB. En entornos reales de despliegue físico perimetral, la comunicación debe ser inalámbrica sobre la red Wi-Fi táctica, resiliente a caídas temporales de señal, de bajo consumo de ancho de banda y capaz de reconectarse automáticamente sin intervención humana.

## 2. Objetivo
Establecer un canal de comunicación inalámbrico bidireccional y robusto basado en el protocolo **MQTT (Message Queuing Telemetry Transport)** entre los nodos Jetson y el Módulo Cerebro, manteniendo alta disponibilidad, detección instantánea de desconexión mediante LWT (Last Will and Testament), transmisión fluida de métricas de hardware y soporte para recepción de alertas de intrusión con snapshots, conservando un fallback automático por HTTP.

## 3. Actores y Usuarios
* **Nodo Jetson (Percepción / Módulo Ojos)**: Dispositivo perimetral que ejecuta YOLO26n y publica métricas de hardware y alertas de intrusión.
* **Módulo Cerebro (FastAPI + Mosquitto)**: Broker central y consumidor que procesa la telemetría, actualiza el estado en memoria, ingesta alertas en PostgreSQL y notifica a la UI vía WebSockets.
* **Operador SOC**: Usuario que supervisa en tiempo real el radar perimetral, estado de hardware y alertas en el panel web.

## 4. Historias de Usuario
* **HU-1**: Como operador SOC, quiero ver en el radar perimetral y en la tarjeta de nodos el estado en línea de la Jetson inmediatamente cuando esta se conecta a la red Wi-Fi, sin necesidad de reiniciar manualmente ningún servicio.
* **HU-2**: Como operador SOC, quiero que el sistema detecte de forma inmediata (< 5 segundos) si una Jetson pierde alimentación o cobertura Wi-Fi, marcándola en estado "Standby / Offline" en el panel.
* **HU-3**: Como nodo Jetson, quiero enviar telemetría de hardware cada 2-3 segundos de forma ultraligera sin bloquear el pipeline de inferencia de visión artificial.
* **HU-4**: Como nodo Jetson, si el broker MQTT no se encuentra disponible temporalmente, quiero conmutar de forma automática al fallback HTTP REST para no perder el reporte de eventos críticos.

---

## 5. Requisitos Funcionales (Notación EARS)

### 5.1 Requisitos Ubicuos (Ubiquitous)
* **RF-UB-01**: El Módulo Cerebro **deberá** desplegar y mantener activo un Broker MQTT (Eclipse Mosquitto) expuesto en el puerto `1883` sobre todas las interfaces de red (incluyendo Wi-Fi `192.168.1.71`).
* **RF-UB-02**: El Módulo Cerebro **deberá** mantener un cliente consumidor MQTT en background dentro de FastAPI que escuche permanentemente los tópicos `sari/nodes/+/telemetry`, `sari/nodes/+/status` y `sari/alerts`.
* **RF-UB-03**: El Broker MQTT **deberá** requerir autenticación básica mediante credenciales configuradas (`sari_operator` / contraseña cifrada o variable de entorno).

### 5.2 Requisitos Basados en Eventos (Event-Driven)
* **RF-EV-01**: **Cuando** un nodo Jetson establezca conexión con el broker MQTT, el nodo **deberá** publicar en el tópico `sari/nodes/{node_id}/status` el mensaje `{"status": "online", "ip": "<ip_wifi>", "timestamp": <unix_ts>}` con bandera `retain=true`.
* **RF-EV-02**: **Cuando** el Módulo Cerebro reciba un mensaje en `sari/nodes/{node_id}/telemetry`, el Módulo Cerebro **deberá** actualizar el diccionario `HardwareState.nodes[node_id]` en memoria con los valores reportados de RAM, CPU, NPU, temperatura y FPS.
* **RF-EV-03**: **Cuando** el Módulo Cerebro reciba un mensaje en `sari/alerts`, el Módulo Cerebro **deberá** procesar el evento de intrusión, registrarlo en la base de datos PostgreSQL, asociar el snapshot fotográfico y emitir la notificación WebSocket a los clientes web conectados.

### 5.3 Requisitos Basados en Estado (State-Driven)
* **RF-SD-01**: **Mientras** el nodo Jetson esté operativo y conectado vía Wi-Fi, el nodo **deberá** publicar métricas de telemetría en `sari/nodes/{node_id}/telemetry` con periodicidad de 3 segundos utilizando **QoS 0**.
* **RF-SD-02**: **Mientras** el Módulo Cerebro esté activo, el endpoint HTTP `POST /api/telemetry/node` y `POST /api/alerts/event` **deberán** permanecer activos y funcionales como respaldo redundante.

### 5.4 Requisitos de Comportamiento No Deseado / Fallos (Unwanted Behavior)
* **RF-UW-01**: **Si** el nodo Jetson pierde abruptamente la conexión Wi-Fi o se apaga, **entonces** el Broker MQTT **deberá** publicar automáticamente el mensaje Last Will and Testament (LWT) en `sari/nodes/{node_id}/status` con `{"status": "offline", "timestamp": <unix_ts>}` (`retain=true`).
* **RF-UW-02**: **Si** el nodo Jetson no logra conectar con el broker MQTT tras 3 reintentos consecutivos, **entonces** el cliente en la Jetson **deberá** enviar sus paquetes a través del endpoint HTTP REST de respaldo (`http://192.168.1.71:8000/api/telemetry/node`) sin interrumpir su ejecución.
* **RF-UW-03**: **Si** el payload recibido en cualquier tópico MQTT es un JSON malformado o excede 5MB, **entonces** el Módulo Cerebro **deberá** descartar el mensaje y registrar un log de advertencia sin detener el servicio.

---

## 6. Criterios de Aceptación
1. **CA-1 (Broker Activo)**: `mosquitto_sub` y `mosquitto_pub` responden exitosamente en el puerto `1883` desde la red local Wi-Fi.
2. **CA-2 (Detección de Caída LWT)**: Al desconectar abruptamente la Jetson (o terminar el proceso de prueba), el estado en el Cerebro cambia a `offline` en menos de 5 segundos.
3. **CA-3 (Telemetría en Vivo)**: El dashboard SOC (`http://localhost:5173/`) refleja en tiempo real la RAM, NPU, Temperatura y FPS transmitidos por Wi-Fi vía MQTT.
4. **CA-4 (Alertas con Snapshot)**: Una alerta publicada en `sari/alerts` con snapshot Base64 crea el mensaje correspondiente en el chat de SARI y actualiza la evidencia visual del intruso.
5. **CA-5 (Persistencia de Servicio en Jetson)**: La Jetson cuenta con un archivo de servicio systemd con política `Restart=always` para garantizar reconexión autónoma tras reinicios.
