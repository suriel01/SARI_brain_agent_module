# Clarificación QA y Casos Límite: Módulo 'Ojos' / 'Eyes' (Spec 003)

## 1. Detección de Ambigüedades y Casos Límite

| ID | Caso Límite / Riesgo | Comportamiento Esperado | Mitigación Técnica |
|---|---|---|---|
| QA-01 | ¿Qué ocurre si un nodo Ojo no tiene stream activo (cámara apagada)? | La tarjeta del nodo muestra 'STANDBY / OFFLINE' con el último timestamp visto y el visor muestra un placeholder profesional con botón de reconectar. | Manejo con `onError` de HTML5 Video/Image + timeout de ping. |
| QA-02 | ¿Qué formato de video soportan los navegadores para streams en vivo? | Los navegadores no soportan RTSP de forma nativa sin transcodificación. | Soportar streams MJPEG directos (como el actual en el puerto 8080) y URLs HTTP/WebRTC. Para RTSP, indicar la necesidad de pasarela o MJPEG en la Jetson. |
| QA-03 | ¿Cómo se almacena una grabación manual en el navegador? | Usar la API nativa de `MediaRecorder` sobre canvas o captura de stream para generar un archivo `.webm` o `.mp4` descargable inmediatamente. | Grabación en cliente sin saturar el ancho de banda del backend. |
| QA-04 | ¿Qué ocurre si se elimina un nodo Ojo que tiene grabaciones/evidencias asociadas? | Las evidencias y mensajes de chat deben preservarse inmutables (Constitución Art. 5). | `ON DELETE CASCADE` solo en configuraciones del nodo, nunca en `chat_messages`. |
| QA-05 | ¿Cómo interactúa el nuevo módulo con el idioma (ES / EN)? | Todas las etiquetas, botones y tooltips deben responder reactivamente a `LanguageContext`. | Centralizar en `translations.ts`. |

## 2. Validación con la Constitución del Proyecto
- **Art. 1 (Stack Simple)**: Sin dependencias pesadas innecesarias. Frontend React + TypeScript, backend FastAPI + SQLAlchemy.
- **Art. 2 (Spec como Ley)**: Los campos de la tabla `eye_nodes` reflejan con exactitud la especificación.
- **Art. 3 (Separación Lógica/Interfaz)**: Los endpoints `/api/eyes` manejan la lógica de negocio y persistencia; el frontend solo consume JSON.
- **Art. 4 (Pruebas Primero)**: Se creará `tests/test_eyes_crud.py` antes de conectar la interfaz.
- **Art. 5 (Persistencia Inmutable)**: Las evidencias de video/fotos se guardan en PostgreSQL y disco.
