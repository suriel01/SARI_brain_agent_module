# Lista de Tareas — Implementación Spec 002 (MQTT Wireless)

> **Regla de Ejecución (Constitución Art. 2 & 4)**: Implementar una tarea a la vez. Primero pruebas/validación, luego código. No avanzar a la siguiente sin verificar la actual.

---

### Fase 1: Infraestructura del Broker Mosquitto
- [x] **T1.1**: Crear configuración y directorio `mosquitto/config/mosquitto.conf` con soporte para puerto 1883, persistencia, límite de mensaje de 10MB y archivo de contraseñas. *(Cubre: RF-UB-01, RF-UB-03)*
- [x] **T1.2**: Incorporar el servicio `sari-mqtt` (imagen `eclipse-mosquitto:2.0`) en `docker-compose.yml` mapeando el puerto `1883:1883` e iniciar el contenedor. *(Cubre: RF-UB-01)*
- [x] **T1.3**: Generar credenciales en `mosquitto/config/passwd` con `mosquitto_passwd` y validar publicación y suscripción local de prueba con autenticación. *(Cubre: RF-UB-03, CA-1)*

### Fase 2: Cliente y Handlers MQTT en el Módulo Cerebro (FastAPI)
- [x] **T2.1**: Añadir dependencia `aiomqtt` o `paho-mqtt` en `backend/requirements.txt` y en `Dockerfile.backend`. *(Cubre: RF-UB-02)*
- [x] **T2.2**: Escribir test de integración `tests/test_mqtt_telemetry.py` que verifique la ingesta de telemetría y actualización en `HardwareState`. *(Cubre: RF-EV-02, Constitución Art. 4)*
- [x] **T2.3**: Implementar el módulo `backend/app/mqtt/client.py` y `backend/app/mqtt/handlers.py` con listeners para `sari/nodes/+/telemetry` y `sari/nodes/+/status` (LWT). *(Cubre: RF-UB-02, RF-EV-01, RF-EV-02, RF-UW-01)*
- [x] **T2.4**: Conectar el ciclo de vida del cliente MQTT en `backend/app/main.py` (inicio en background y apagado limpio). *(Cubre: RF-UB-02)*
- [x] **T2.5**: Ejecutar `pytest tests/test_mqtt_telemetry.py` y validar que el test pasa en verde. *(Cubre: CA-1, CA-2)*

### Fase 3: Procesamiento de Alertas con Snapshot vía MQTT
- [x] **T3.1**: Escribir test `tests/test_mqtt_alerts.py` que publique una alerta con snapshot en Base64 y verifique persistencia en PostgreSQL y broadcast WebSocket. *(Cubre: RF-EV-03, Constitución Art. 4 & 5)*
- [x] **T3.2**: Implementar el handler para `sari/alerts` en `backend/app/mqtt/handlers.py` reutilizando la lógica transaccional de alertas con `SessionLocal()`. *(Cubre: RF-EV-03, CA-4)*
- [x] **T3.3**: Ejecutar `pytest tests/test_mqtt_alerts.py` y validar resultado en verde. *(Cubre: CA-4)*

### Fase 4: Script Dual y Servicio Persistente para la Jetson
- [x] **T4.1**: Actualizar `jetson_telemetry.py` incorporando cliente MQTT con LWT, publicación periódica a `sari/nodes/{node_id}/telemetry` y fallback automático a HTTP REST. *(Cubre: RF-SD-01, RF-UW-02)*
- [x] **T4.2**: Probar la simulación de caída de conexión MQTT y verificar que el fallback HTTP conmuta sin pérdida de telemetría. *(Cubre: RF-UW-02, CA-3)*
- [x] **T4.3**: Generar el prompt final y el archivo de servicio `sari-jetson.service` para el agente de la Jetson. *(Cubre: CA-5)*

### Fase 5: Validación E2E en Dashboard SOC
- [x] **T5.1**: Enviar telemetría MQTT simulada representando la Jetson por Wi-Fi y verificar visualmente en `http://localhost:5173/` (Radar con pulso verde, RAM con barra y telemetría de CPU/GPU). *(Cubre: CA-3)*
- [x] **T5.2**: Simular desconexión forzada (LWT) y validar que el nodo pasa a `STANDBY` en menos de 5 segundos. *(Cubre: CA-2)*
- [x] **T5.3**: Generar reporte de walkthrough final con capturas del broker y la interfaz.
