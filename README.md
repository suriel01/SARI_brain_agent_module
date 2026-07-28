# 🛡️ SARI Brain Agent — Sistema Autónomo de Respuesta a Intrusiones

**SARI (Sistema Autónomo de Respuesta a Intrusiones)** es una plataforma de seguridad perimetral autónoma de nivel empresarial que combina Inteligencia Artificial local, visión por computadora en tiempo real (**NVIDIA Jetson Orin Nano con YOLO26n**), control de hardware físico, guardrails de seguridad de IA (**NeMo Guardrails**) y una consola gráfica táctica para Centro de Operaciones de Seguridad (SOC).

---

## 🚀 Características Principales

### 🎨 1. Consola Táctica SOC Tono Oscuro Monocromático
- **Estética SOC Profesional**: Diseño táctico en escalas de grises oscuros puros (`#090a0f`, `#13151c`), reduciendo la fatiga visual y reservando el color **Azul de Acción (`#0284c7`)** únicamente para botones ejecutables (`+ New Chat`, `Logout`, `Send`, `Autorizar PIN`).
- **Fondo Animado de Circuitos (`CircuitCanvas`)**: Lienzo HTML5 Canvas con cuadrícula minimalista y partículas viajando suavemente en tiempo real a lo largo de las trazadas, visible a través de los paneles traslúcidos con efecto *glassmorphism* (`backdrop-filter: blur(12px)`).
- **Paneles Plegables y Redimensionables**:
  - Barra lateral de Módulos (Chat, Live Perception, Hardware Control, User Management) redimensionable por arrastre y plegable hasta ocultarse por completo.
  - Barra lateral de Hilos de Chat independiente con límites de expansión/contracción y botones tácticos de despliegue en un solo clic.

---

### 🛡️ 2. Seguridad del Agente con NeMo Guardrails
- **Protección Táctica Activa**: Implementación de guardrails mediante **NeMo Guardrails (`actions.co`)** para la interceptación y validación de prompts, bloqueando intentos de inyección de comandos o fugas de información interna.
- **Ocultamiento de Stack Técnico por Seguridad**: El agente y la interfaz reportan el estado con la insignia **`LLM Online`**, garantizando la privacidad de los modelos e infraestructura subyacente.
- **Guardrail para Reportes de Estatus Tácticos**: Al solicitar *"dame un reporte de estatus"*, el sistema desglosa un informe ejecutivo completo en formato Markdown que incluye:
  - Estado de componentes principales (Backend, PostgreSQL/pgvector, Sirena, NeMo Guardrails).
  - Sección dedicada a **Módulos de Visión Táctica Jetson Orin Nano / Nodos**, indicando su estado de conexión (`ONLINE`) y de grabación (`REC 1080p`).
  - Historial reciente de intrusiones en memoria RAG.
  - Evaluación de nivel de amenaza y permisos del usuario autenticado (RBAC).

---

### 📸 3. Captura de Módulos y Evidencia por Chat
- **Solicitud de Capturas en Tiempo Real**: El operador puede pedir capturas directamente al agente (*"muéstrame capturas del módulo X"*, *"envía una captura de la intrusión"*), desplegando imágenes de evidencia formateadas en el chat.
- **Recepción de Alertas Automáticas Jetson**: Al detectar una intrusión, los nodos NVIDIA Jetson envían una notificación que genera un hilo de evidencia e imágenes asociadas.

---

### 📋 4. Registro de Event Logs con Filtros y Caducidad (TTL)
- **Fechado Preciso**: Cada mensaje enviado por el usuario o generado por el agente incluye la fecha y hora fija exacta (`YYYY-MM-DD HH:MM:SS`).
- **Logs de Auditoría**: Toda acción (login, disparos de alarma, bloqueos, cambios de estado) se registra automáticamente en los Event Logs.
- **Búsqueda y Filtros Granulares**:
  - Filtro por Nivel de Severidad (`ALL`, `INFO`, `WARN`, `CRITICAL`).
  - Filtro por Módulo Origen (`System`, `Vision Node`, `Hardware`, `Auth`).
  - Búsqueda por texto en tiempo real y selector de Rango de Fechas.
- **Tiempo de Vida / Caducidad (TTL)**: Mecanismo automatizado para la depuración de logs obsoletos.

---

### 🚨 5. Barra de Emergencia de 2 Capas & Control de Hardware
- **1-Click Emergency Toolbar**: Acceso rápido desde la cabecera superior a los controles críticos del perímetro:
  - **Sirena Sonora Perimetral**: Disparo manual/automático de la alarma física y sintetizador de audio táctico en navegador. Indicador dinámico en Verde (Normal) / Rojo (Alerta Activa).
  - **Bloqueo Perimetral de Accesos**: Cierre y enclavamiento de portones. Indicador en Ámbar cuando está activado.
- **Protección con PIN de Seguridad (`1234`)**: Las acciones sensibles requieren autorización previa mediante un modal con clave de seguridad.
- **Control PTZ y Telemetría**: Monitoreo de cámaras con controles de movimiento (Pan/Tilt/Zoom) e indicadores de estado de red.

---

### 👥 6. Matriz de Permisos Granulares (RBAC)
- **Roles de Administrador y Operador**: Control estricto de acceso basado en el rol del usuario autenticado.
- **Permisos Granulares**: Creación, renombrado y eliminación de hilos de chat, control de hardware y administración de cuentas de usuario.

---

## 🛠️ Requisitos Previos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

---

## ⚡ Inicio Rápido (Despliegue con Docker)

1. Clonar el repositorio:
   ```bash
   git clone git@github.com:suriel01/SARI_brain_agent_module.git
   cd SARI_brain_agent_module
   ```

2. Levantar la infraestructura completa con Docker Compose:
   ```bash
   docker compose up -d --build
   ```

3. Abrir la consola táctica en el navegador:
   👉 **[http://localhost:5173](http://localhost:5173)**

### 🔑 Credenciales Iniciales por Defecto

- **Usuario Administrador**: `admin`
- **Contraseña**: `sari_password`
- **PIN de Seguridad para Hilos/Acciones**: `1234`

---

## 📡 Integración con Nodos Jetson Orin Nano (YOLO26n)

Los nodos de visión artificial envían alertas en tiempo real mediante peticiones HTTP POST al backend:

```bash
curl -X POST http://localhost:7000/api/alerts/event \
  -H "Content-Type: application/json" \
  -d '{
    "module_name": "Jetson-Orin-Nano-01",
    "event": "Intrusión de vehículo no autorizado",
    "confidence": 0.98,
    "auto_siren": true
  }'
```

---

## 📂 Estructura del Proyecto

```
SARI_brain_agent/
├── backend/
:   ├── app/
│   │   ├── crud/           # Lógica de operaciones en PostgreSQL
│   │   ├── guardrails/     # Definiciones NeMo Guardrails (actions.co, config.yml)
│   │   ├── models/         # Modelos SQLAlchemy (User, ChatThread, ChatMessage, EventLog)
│   │   ├── routers/        # Rutas de API (auth, chat, users, hardware, alerts)
│   │   ├── schemas/        # Esquemas Pydantic
│   │   └── main.py         # Punto de entrada FastAPI
│   └── Dockerfile.backend
├── sari-ui/                # Consola Frontend React + TypeScript
│   ├── src/
│   │   ├── components/     # Dashboard, ChatPanel, HardwarePanel, AdminPanel, CircuitCanvas, PinModal
│   │   └── index.css       # Estilos del SOC Monocromático
│   └── Dockerfile
├── sirena_service.py       # Microservicio HTTP de sirena sonora física
├── Dockerfile.sirena
├── docker-compose.yml      # Orquestador Docker (PostgreSQL, Backend, UI, Sirena)
└── README.md
```

---

## 📜 Licencia

Desarrollado para la infraestructura de seguridad autónoma **SARI**. Todos los derechos reservados.
