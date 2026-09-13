# Especificación Funcional (EARS): Módulo 'Ojos' / 'Eyes' (Spec 003)

## 1. Contexto y Visión
El módulo 'Percepción en Vivo' se renombra y evoluciona hacia **'Ojos'** (**'Eyes'** en inglés), convirtiéndose en el Centro de Control y Gestión de Módulos Perimetrales Jetson del sistema SARI. Este panel centraliza el streaming en vivo, la telemetría táctica de hardware, la gestión de grabaciones/evidencias y un asistente de emparejamiento para conectar nuevos módulos Jetson a la red.

---

## 2. Requisitos del Sistema (Sintaxis EARS)

### 2.1 Requisitos Ubicuos (Ubiquitous Requirements)
- **RF-UB-01**: El sistema SIEMPRE mostrará el identificador del módulo como 'Ojos' en español y 'Eyes' en inglés en la barra lateral de navegación y en la cabecera del panel.
- **RF-UB-02**: El sistema SIEMPRE mantendrá persistidos en PostgreSQL los nodos Ojos registrados con su nombre, identificador, dirección IP, URL de stream y umbral YOLO.
- **RF-UB-03**: El sistema SIEMPRE combinará los datos estáticos del nodo en base de datos con la telemetría en tiempo real recibida por MQTT/HTTP.

### 2.2 Requisitos Basados en Eventos (Event-Driven Requirements)
- **RF-EV-01**: CUANDO el operador seleccione una tarjeta de Nodo Ojo en el selector superior, el sistema cargará inmediatamente su transmisión de video y sus métricas de telemetría correspondientes.
- **RF-EV-02**: CUANDO el operador presione el botón 'Grabar (REC)', el sistema iniciará una captura de video con contador activo en tiempo real y permitirá detenerla para descargarla o guardarla.
- **RF-EV-03**: CUANDO el operador abra el modal 'Conectar Nuevo Ojo', el sistema presentará un formulario con validación, prueba de conexión y botón para copiar las credenciales/script de configuración para esa Jetson.
- **RF-EV-04**: CUANDO se reciba una alerta de intrusión con snapshot desde un nodo, el sistema la registrará automáticamente en la sección de 'Historial de Grabaciones y Evidencias'.

### 2.3 Requisitos Basados en Estado (State-Driven Requirements)
- **RF-SD-01**: MIENTRAS el stream de video esté activo, el HUD mostrará el estado de enlace ('EN VIVO' / 'LIVE' con pulso esmeralda), resolución, FPS y controles de orientación (rotación 90°, Flip H, Flip V, Pantalla Completa).
- **RF-SD-02**: MIENTRAS un nodo esté desconectado o en fallo de red, el sistema mostrará el badge 'STANDBY' / 'OFFLINE' y ofrecerá botón de 'Reconectar'.

### 2.4 Requisitos Opcionales / Deseables (Optional Feature Requirements)
- **RF-OP-01**: DONDE sea posible, el sistema ofrecerá una vista de mosaico rápido para visualizar múltiples Ojos de forma simultánea.

---

## 3. Criterios de Aceptación (Acceptance Criteria)
- **CA-1**: La pestaña y cabecera deben cambiar de 'Percepción en Vivo' / 'Live Perception' a 'Ojos' / 'Eyes' según el idioma activo.
- **CA-2**: La tabla `eye_nodes` debe guardar y listar permanentemente los nodos en PostgreSQL.
- **CA-3**: El nodo predeterminado `Jetson-PTZ_1` debe venir precargado y funcional con el stream `http://192.168.55.1:8080/mjpeg`.
- **CA-4**: El asistente modal 'Conectar Nuevo Ojo' debe permitir agregar un nuevo nodo con prueba de conexión y persistencia inmediata sin recargar la página.
- **CA-5**: El botón de grabación en vivo (REC) debe permitir capturar clips y el visor de grabaciones debe mostrar las evidencias de intrusión con fecha y descarga.
