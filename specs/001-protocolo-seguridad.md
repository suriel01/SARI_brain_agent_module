
# Especificación: Protocolo de Seguridad SARI (Odysseus Agent)

Este documento detalla las reglas de operación y prioridades del Agente IA `SARI Cerebro` configurado en Odysseus.

---

## 1. Misión

Monitorear las alertas perimetrales emitidas por el Módulo Ojo (Jetson) y neutralizar amenazas coordinando alarmas, bloqueos físicos y notificaciones de emergencia.

---

## 2. Protocolo de Actuación ante Alertas

Cuando el webhook recibe una notificación de intrusión:

### Paso 1: Evaluación del Nivel de Riesgo

- **Riesgo Bajo**: Detección única de 1 persona durante el horario laboral (8:00 AM - 6:00 PM).
  * *Acción*: Registrar en bitácora, sin alarmas.
- **Riesgo Medio**: Detección de 1 a 2 personas fuera del horario laboral o comportamiento errático.
  * *Acción*: Notificar por Telegram de forma preventiva.
- **Riesgo Alto (Intrusión Confirmada)**: Detección de 3 o más personas concurrentes, o permanencia prolongada (>15s) en áreas restringidas.
  * *Acción*: Disparar protocolo de respuesta inmediata.

### Paso 2: Protocolo de Respuesta Inmediata (Riesgo Alto)

1. **Bloqueo Perimetral**: Invocar herramienta MCP `cerrar_accesos`.
2. **Disuasión Sonora**: Invocar herramienta MCP `activar_sirena` (duración: 60 segundos).
3. **Anulación PTZ (Freeze)**: Hacer un POST al Gateway (`http://localhost:5000`) con el payload `{"comando": "set_tracking", "estado": false}` para que la cámara congele su posición y grabe el ángulo fijo de la intrusión.
4. **Notificación de Emergencia**: Disparar alerta externa a Telegram con detalles del evento (número de intrusos detectados).
