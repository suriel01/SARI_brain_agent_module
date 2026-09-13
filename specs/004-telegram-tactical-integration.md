# Especificación Funcional (EARS): Módulo Telegram Táctico y Watchdog Anti-Sabotaje (Spec 004)

## 1. Contexto y Visión
El Módulo Cerebro SARI debe extender su capacidad operativa hacia dispositivos móviles de los operadores mediante un bot de Telegram seguro y bidireccional. Esta integración permite la notificación instantánea de intrusiones con evidencia fotográfica, la ejecución de órdenes tácticas en lenguaje natural o mediante comandos rápidos, y un sistema watchdog anti-sabotaje que detecta al instante la desconexión involuntaria de cualquier Módulo Ojo (Jetson).

---

## 2. Requisitos del Sistema (Sintaxis EARS)

### 2.1 Requisitos Ubicuos (Ubiquitous Requirements)
- **RF-UB-01**: El sistema SIEMPRE verificará que el remitente en Telegram pertenezca a la lista blanca (`TELEGRAM_ALLOWED_CHAT_IDS`) antes de procesar cualquier comando o consulta.
- **RF-UB-02**: El sistema SIEMPRE registrará las interacciones de Telegram en un hilo de auditoría dedicado en PostgreSQL ('🤖 Telegram Operator Chat').
- **RF-UB-03**: El sistema SIEMPRE requerirá el PIN de seguridad `1234` para ejecutar órdenes con impacto físico (activar sirena, bloquear accesos) emitidas desde Telegram.

### 2.2 Requisitos Basados en Eventos (Event-Driven Requirements)
- **RF-EV-01**: CUANDO se reciba una alerta de intrusión desde cualquier Módulo Ojo (YOLO), el sistema enviará inmediatamente un mensaje prioritario a Telegram con el snapshot adjunto en alta resolución y botones de acción rápida.
- **RF-EV-02**: CUANDO un Módulo Ojo o Agente sufra una desconexión abrupta (notificada vía MQTT LWT o detectada por el Watchdog tras 15 segundos sin telemetría), el sistema enviará una alerta crítica a Telegram indicando '🚨 POSIBLE SABOTAJE / INTRUSIÓN' adjuntando la última evidencia fotográfica conocida.
- **RF-EV-03**: CUANDO el operador envíe un comando rápido (`/status`, `/sirena [PIN]`, `/silenciar`, `/portones [PIN]`, `/foto [nodo]`), el sistema ejecutará la acción correspondiente y devolverá una confirmación formateada en menos de 1 segundo.
- **RF-EV-04**: CUANDO el operador envíe una consulta en lenguaje natural (ej. '¿cuál es la situación del perímetro?', '¿hay cámaras en standby?'), el sistema canalizará el texto a través del motor LLM de SARI (Ollama + Guardrails) y devolverá la respuesta táctica al chat.

### 2.3 Requisitos Basados en Estado (State-Driven Requirements)
- **RF-SD-01**: MIENTRAS el servicio de backend esté en ejecución, un hilo background mantendrá polling activo con la API de Telegram para procesar comandos sin requerir webhooks públicos ni apertura de puertos WAN.
- **RF-SD-02**: MIENTRAS un nodo esté desconectado, el watchdog evitará enviar alertas duplicadas recurrentes (de-bouncing), emitiendo una única notificación por evento de caída hasta que el nodo se reincorpore a la red.

### 2.4 Requisitos de Manejo de Fallos (Unwanted Behavior / Fallback)
- **RF-UW-01**: SI el servidor no dispone de conexión a internet o la API de Telegram no responde, el sistema registrará la incidencia en el registro de auditoría local de `HardwareState` sin bloquear el flujo principal de seguridad ni el SOC dashboard.

---

## 3. Criterios de Aceptación (Acceptance Criteria)
- **CA-1**: Las alertas de detección YOLO deben enviarse a Telegram con texto y foto en base64 convertida a JPEG.
- **CA-2**: La desconexión de una Jetson (LWT o caída de heartbeat > 15s) debe disparar una alerta de posible sabotaje a Telegram en menos de 5 segundos.
- **CA-3**: Los comandos `/status`, `/sirena 1234`, `/silenciar` y `/foto` deben responder de forma interactiva en Telegram.
- **CA-4**: Los mensajes que no comiencen con barra `/` deben ser respondidos por el modelo de IA de SARI.
- **CA-5**: Los usuarios de Telegram no autorizados deben recibir un mensaje de rechazo de acceso ('Acceso no autorizado').
