# Fase de Clarificación y Auditoría de QA — Spec 002

**Rol**: QA Lead & Architecture Reviewer  
**Documento Evaluado**: [`specs/002-mqtt-wireless-telemetry.md`](file:///home/surielalcantara/Desktop/SARI_Agent_Odysseus/specs/002-mqtt-wireless-telemetry.md)  
**Base Normativa**: [`doc/constitution.md`](file:///home/surielalcantara/Desktop/SARI_Agent_Odysseus/doc/constitution.md)

---

## 1. Detección de Ambigüedades
* **A-1 (Límite de Tamaño de Snapshot en Mosquitto)**: Por defecto, Mosquitto permite payloads de hasta 256MB, pero si no se define explícitamente `message_size_limit` en `mosquitto.conf`, una ráfaga de imágenes JPEG en Base64 de alta resolución (>2MB) podría consumir memoria del broker de forma imprevista si se retienen mensajes.
* **A-2 (Sincronización de Base de Datos en Alertas MQTT)**: El hilo de recepción MQTT en FastAPI corre como tarea asíncrona o subproceso. La ingesta de la alerta en PostgreSQL debe gestionar sesiones de SQLAlchemy independientes (`scoped_session` o `SessionLocal`) para evitar conflictos de concurrencia con el pool de conexiones del servidor HTTP/Uvicorn.
* **A-3 (Retain flag en Alertas)**: Las alertas de intrusión **NO deben** llevar `retain=true`. Si llevaran retain, cualquier nuevo cliente o reconexión del Cerebro procesaría una intrusión vieja como si fuera nueva.

## 2. Casos Límite y Escenarios de Borde No Cubiertos
* **CL-1 (Reconexión Intermitente / Flapping Wi-Fi)**: Si la señal Wi-Fi de la Jetson oscila rápidamente, el LWT y el connect podrían dispararse múltiples veces por minuto. El Cerebro debe ignorar transiciones repetidas con una ventana de amortiguación (debounce) de 3 segundos.
* **CL-2 (Doble Envío MQTT + HTTP)**: Si la Jetson tiene configurado fallback, no debe enviar el mismo evento simultáneamente por ambos canales para evitar alertas duplicadas en el SOC.
* **CL-3 (Sincronización Horaria)**: Al trabajar sobre Wi-Fi sin acceso a internet (Constitución Art. 6), los relojes de la Jetson y el Cerebro podrían tener desfase si no hay un servidor NTP local. El Cerebro debe estampar su propia marca temporal de recepción para la persistencia oficial.

## 3. Conformidad con la Constitución
| Principio Constitucional | Estado | Observación |
| :--- | :---: | :--- |
| **1. Simplicidad del Stack** | ✅ Cumple | Mosquitto es el estándar de oro ligero en C; se integra en Docker Compose sin sobrecarga. |
| **2. Spec-First** | ✅ Cumple | Spec 002 cubre todas las historias y requisitos antes de tocar código. |
| **3. Separación Lógica/Transporte** | ✅ Cumple | El handler de MQTT invoca la misma función de negocio `record_node_activity` y `process_alert_event` que el endpoint HTTP. |
| **4. Política de Tests** | ⚠️ Condicionado | El plan técnico debe incluir tests automatizados de publicación/suscripción MQTT con cliente mock y test de integración en broker real. |
| **5. Persistencia e Integridad** | ✅ Cumple | Telemetría se mantiene en memoria (`HardwareState`); alertas se persisten en PostgreSQL. |
| **6. Resiliencia Offline** | ✅ Cumple | Broker local en `192.168.1.71` sin salida a internet + fallback a HTTP local. |

---

## 4. Resoluciones Técnicas Incorporadas al Plan
1. Se añadirá `message_size_limit 10485760` (10MB) en la configuración de Mosquitto para snapshots con margen holgado.
2. `sari/alerts` se publicará con `retain=false` y `QoS=1`.
3. El cliente MQTT del Cerebro gestionará `SessionLocal()` con bloque `try/finally` para asegurar el cierre de la conexión a PostgreSQL tras cada alerta procesada.
