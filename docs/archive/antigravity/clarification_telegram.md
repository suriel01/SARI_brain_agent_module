# Clarificación QA y Casos Límite: Integración Telegram y Watchdog (Spec 004)

## 1. Detección de Ambigüedades y Casos Límite

| ID | Caso Límite / Riesgo | Comportamiento Esperado | Mitigación Técnica |
|---|---|---|---|
| QA-01 | ¿Qué ocurre si se envían múltiples mensajes de LWT por parpadeo de red Wi-Fi? | No debe haber inundación (spam) de alertas en Telegram. | Bandera de estado `notified_disconnection` por `node_id`. Solo se resetea cuando el nodo envía telemetría válida nuevamente. |
| QA-02 | ¿Cómo convertir la imagen en Base64 para enviarla a Telegram? | Telegram `sendPhoto` requiere un archivo binario multipart/form-data o una URL pública. | Decodificar el string base64 (`base64.b64decode`) en un buffer en memoria (`io.BytesIO`) y enviarlo con `files={'photo': ('snapshot.jpg', bio, 'image/jpeg')}`. |
| QA-03 | ¿Cómo manejar comandos físicos sin PIN en Telegram? | Si el usuario envía `/sirena` sin PIN o un comando como "activa la sirena", SARI responderá: "⚠️ Se requiere el PIN de seguridad de 4 dígitos para ejecutar esta acción táctica. Escribe `/sirena [PIN]`". | Validación centralizada con `SARI_SECURITY_PIN` (1234). |
| QA-04 | ¿Qué pasa si el servidor Cerebro pierde conexión a internet? | Telegram requiere salida a internet (`api.telegram.org`), pero SARI es offline-first (Constitución Art. 6). | El hilo de Telegram usa `try/except` con timeouts cortos (3.0s). Si falla, añade un log `WARN` a `HardwareState.add_log` y continúa operando localmente sin interrumpir sirenas ni el SOC Dashboard. |
| QA-05 | ¿Cómo responder a callbacks de botones inline? | Los botones inline envían `callback_query`. El bot debe responder con `answerCallbackQuery` y ejecutar la acción táctica asociada si tiene permiso. | Handler para `callback_query` en el bucle de polling. |

## 2. Validación con la Constitución del Proyecto
- **Art. 1 (Stack Simple)**: Sin frameworks pesados. Cliente asíncrono puro con `requests`/`httpx` en un hilo daemon de FastAPI.
- **Art. 2 (Spec como Ley)**: Comandos y formatos respetan estrictamente la sintaxis definida.
- **Art. 3 (Separación Lógica/Interfaz)**: Los comandos de Telegram invocan las mismas funciones de negocio (`execute_physical_tool`, `HardwareState`, LLM pipeline).
- **Art. 4 (Pruebas Primero)**: Se creará `tests/test_telegram_service.py` simulando la API de Telegram para verificar procesamiento de comandos y alertas.
- **Art. 5 (Persistencia Inmutable)**: Las alertas y comandos se auditan en PostgreSQL.
- **Art. 6 (Autonomía Offline)**: Ninguna falla de Telegram puede congelar el procesamiento local ni las sirenas físicas.
