# Constitución del Ecosistema SARI (Sistema Autónomo de Respuesta a Intrusiones)

Este documento define las reglas innegociables, cortas y verificables que rigen todo el desarrollo, arquitectura y evolución del Módulo Cerebro y sus nodos perimetrales.

---

## 1. Simplicidad del Stack (KISS & Minimalismo Operativo)
* Ninguna dependencia o servicio externo se incorporará al sistema a menos que resuelva un cuello de botella comprobado.
* Todo componente debe ser reproducible mediante contenedores ligeros en `docker-compose.yml` sin configuraciones ocultas.
* Se priorizan protocolos estándar y probados en la industria (MQTT para IoT/mensajería perimetral, HTTP/REST para control transaccional, WebSockets para la UI).

## 2. Relación Estricta entre Spec y Código (Spec-First)
* Queda estrictamente prohibido escribir o modificar código de producción sin una especificación funcional aprobada en `specs/`.
* Todo cambio en la lógica de negocio, modelo de datos o contratos de red debe reflejarse primero en su especificación antes de la implementación.
* Cualquier código que no responda directamente a un requisito funcional de una spec se considera deuda técnica y debe ser retirado.

## 3. Separación Total entre Lógica, Transporte e Interfaz
* Los adaptadores de comunicación (MQTT Broker, REST API, WebSockets) son mecanismos de transporte intercambiables; la lógica de negocio y las alertas tácticas deben residir desacopladas en el núcleo del servicio.
* El frontend (SOC Dashboard) es una vista reactiva del estado del sistema y nunca debe contener lógica de negocio, cómputo de reglas tácticas ni orquestación de hardware.

## 4. Política de Tests y Validación Reproducible
* Toda nueva funcionalidad de backend debe contar con tests unitarios o de integración automatizados que validen tanto el camino feliz como los casos de borde (desconexión, timeout, payloads malformados).
* Primero se define la verificación (test o comando de validación reproducible), luego se escribe el código de producción. Ninguna tarea se da por concluida sin ejecución y reporte verde de sus pruebas.

## 5. Persistencia de Datos e Integridad Histórica
* Todo evento táctico de intrusión, alerta física y acción manual sobre hardware debe registrarse de manera persistente e inmutable en PostgreSQL.
* La telemetría efímera de alta frecuencia (heartbeats periódicos) se procesará en memoria y actualizará el estado activo (`HardwareState`), pero nunca saturará la base de datos con escrituras innecesarias.

## 6. Resiliencia Operativa Offline y Degradación Elegante
* El sistema opera bajo la directiva estricta de **cero dependencia de internet**: todos los servicios (LLM Ollama, Mosquitto MQTT, FastAPI, PostgreSQL, Sirenas) deben arrancar y funcionar en una red perimetral aislada.
* Todo cliente perimetral (nodos Jetson) debe implementar reintento infinito y mecanismos de degradación elegante (fallback automático a HTTP si MQTT no responde, y almacenamiento en buffer local si el canal se interrumpe).
