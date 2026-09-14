# Lista de Tareas — Implementación Spec 004 (Telegram Táctico & Watchdog)

> **Regla de Ejecución (Constitución Art. 2 & 4)**: Implementar una tarea a la vez. Primero pruebas/validación, luego código. No avanzar a la siguiente sin verificar la actual.

---

### Fase 1: Servicio Core de Telegram y Variables de Entorno
- [x] **T1.1**: Configurar variables `TELEGRAM_BOT_TOKEN` y `TELEGRAM_ALLOWED_CHAT_IDS` en `docker-compose.yml` y soporte en `.env`. *(Cubre: RF-UB-01)*
- [x] **T1.2**: Escribir test de integración `tests/test_telegram_service.py` con simulación (mock) de la API de Telegram para verificar whitelist, ejecución de comandos y respuesta con LLM. *(Cubre: RF-UB-01, RF-EV-03, Constitución Art. 4)*
- [x] **T1.3**: Implementar el módulo `backend/app/telegram/service.py` con funciones `send_telegram_message`, `send_telegram_alert_photo` y validación de seguridad. *(Cubre: RF-EV-01, RF-UB-01)*

### Fase 2: Bot Bidireccional y Modo Dual Híbrido (Polling + Comandos + LLM)
- [x] **T2.1**: Implementar el bucle de polling y dispatcher de comandos (`/status`, `/sirena`, `/silenciar`, `/portones`, `/foto`) en `backend/app/telegram/bot.py`. *(Cubre: RF-EV-03, RF-SD-01)*
- [x] **T2.2**: Integrar el pipeline LLM de SARI (NeMo Guardrails + Ollama `qwen2.5:7b`) para procesar consultas en lenguaje natural desde Telegram. *(Cubre: RF-EV-04, RF-UB-02)*
- [x] **T2.3**: Conectar el ciclo de vida del bot en `backend/app/main.py` (`startup` y `shutdown`). *(Cubre: RF-SD-01)*

### Fase 3: Watchdog Anti-Sabotaje por Desconexión de Nodos
- [x] **T3.1**: Escribir test `tests/test_watchdog_disconnection.py` que simule la desconexión abrupta de una Jetson y verifique el envío de la alerta crítica a Telegram. *(Cubre: RF-EV-02, CA-2)*
- [x] **T3.2**: Conectar el handler de status MQTT (`sari/nodes/+/status`) para que el evento LWT `offline` dispare inmediatamente la alerta a Telegram con la última evidencia. *(Cubre: RF-EV-02)*
- [x] **T3.3**: Implementar el bucle de Watchdog en background (timer 15s) en `backend/app/telegram/watchdog.py` para detectar caídas silenciosas de telemetría. *(Cubre: RF-EV-02, RF-SD-02)*

### Fase 4: Integración con Alertas YOLO en Tiempo Real
- [x] **T4.1**: Conectar el handler `sari/alerts` (y `/api/alerts/event`) para que cada intrusión detectada envíe la alerta enriquecida con foto a Telegram además del guardado en PostgreSQL. *(Cubre: RF-EV-01, CA-1)*
- [x] **T4.2**: Probar la recepción de alerta simulada y verificar la entrega del mensaje formateado con botones de acción rápida. *(Cubre: CA-1)*

### Fase 5: Validación Integral y Pruebas
- [x] **T5.1**: Ejecutar la suite completa de tests automatizados (`pytest tests/test_telegram_service.py tests/test_watchdog_disconnection.py`). *(Cubre: CA-2, CA-3, CA-4)*
- [x] **T5.2**: Elaborar walkthrough documentando la configuración, comandos soportados y guía para pegar el Bot Token y Chat ID en `.env`.
