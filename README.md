# 🛡️ SARI Brain Agent — Sistema Autónomo de Respuesta a Intrusiones

**SARI (Sistema Autónomo de Respuesta a Intrusiones)** es una plataforma de defensa y seguridad perimetral táctica de nivel empresarial. Integra Inteligencia Artificial local, visión por computadora en tiempo real (**NVIDIA Jetson Orin Nano con YOLO26n**), telemetría inalámbrica MQTT, control de hardware táctico, guardrails de seguridad de IA (**NeMo Guardrails**), un bot táctico interactivo en **Telegram** y una consola gráfica de operaciones (**SOC Dashboard**).

---

## 🏛️ Arquitectura Global del Sistema

```
  ┌─────────────────────────────────────────────────────────────┐
  │                 PERÍMETRO / NODOS DE VISIÓN                │
  │                                                             │
  │   [NVIDIA Jetson Orin Nano] (Módulo Ojos)                  │
  │     ├── YOLO26n: Inferencia local en vivo                   │
  │     ├── jetson_telemetry.py: Telemetría CPU/GPU/RAM/Temp/FPS│
  │     └── Publicador MQTT con Last Will and Testament (LWT)   │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ Wi-Fi / Ethernet
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │              INFRAESTRUCTURA SARI CEREBRO (HOST)            │
  │                                                             │
  │   [Broker MQTT Mosquitto] (Puerto 1883)                     │
  │     └── sari/nodes/+/telemetry | sari/alerts | status (LWT) │
  │                                                             │
  │   [FastAPI Backend] (Puerto 7000)                           │
  │     ├── Watchdog de Desconexión y Anti-Sabotaje             │
  │     ├── NeMo Guardrails & Inferencia LLM Offline            │
  │     ├── WebSocket & API REST para SOC Dashboard             │
  │     └── Motor de Integración Bidireccional con Telegram     │
  │                                                             │
  │   [PostgreSQL 15 + pgvector] (Puerto 5433)                  │
  │     └── Persistencia de chats, usuarios, eventos y nodos    │
  │                                                             │
  │   [Microservicio de Sirena Táctica] (Puerto 5000)           │
  │     └── Control de bocina física y disparo de pulsos        │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌──────────────────────────────┐         ┌──────────────────────────────┐
│     SOC DASHBOARD (VITE)     │         │     TELEGRAM BOT TÁCTICO     │
│       Puerto 5173            │         │                              │
│  • Chat Táctico con Agente   │         │  • Alertas Críticas Push     │
│  • Ojos: Métricas & Config   │         │  • Botones de Acción Inline  │
│  • Control: Radar Perimetral │         │  • Comandos remotos          │
│  • Usuarios: Matriz RBAC     │         │  • Capturas (/fotos, /foto)  │
└──────────────────────────────┘         └──────────────────────────────┘
```

---

## 🚀 Características Principales del Ecosistema

### 1. 🎛️ Consola Táctica SOC Dashboard (React + TypeScript)
- **Modo Oscuro Monocromático & Alto Rendimiento**: Estética táctica militar inspirada en centros de mando de operaciones de seguridad.
- **Módulos Principales (Bilingüe ES / EN)**:
  - **Chat**: Comunicación segura con el agente SARI Cerebro, visor de evidencias fotográficas con relación de aspecto natural e historial persistente.
  - **Ojos (Eyes)**: Supervisión y administración centralizada de todas las cámaras Jetson. Despliegue de métricas en vivo (RAM usada/total, CPU %, GPU %, Temperatura, FPS, tipo de enlace), galería de evidencias por nodo y modal de configuración protegida por PIN (renombrar cámara, ajustar umbral de confianza YOLO, modo de detección).
  - **Control**: Escaneo radar perimetral interactivo. Muestra exclusivamente los nodos en línea con pulso táctico verde; al pulsar sobre un nodo en el radar, conmuta directamente a la sección de configuración de esa Jetson en el módulo Ojos.
  - **Usuarios (Users)**: Matriz de Control de Acceso Basado en Roles (RBAC) con permisos granulares (crear hilos, eliminar hilos, control de hardware, administración de cuentas).
- **Pantalla de Inicio de Sesión Táctica**: Presentación minimalista con logotipo SARI en alta resolución, interfaz oscura, pie de versión `SARI OS V0.5` y selector de idioma dinámico.

---

### 2. 📡 Telemetría Inalámbrica y Red de Sensores (MQTT Broker)
- **Broker Eclipse Mosquitto Contenedorizado**: Expuesto en el puerto `1883` con autenticación segura y soporte para transferencia de evidencia fotográfica (hasta 10 MB).
- **Tópicos Estandarizados**:
  - `sari/nodes/{node_id}/telemetry`: Reporte periódico de salud de hardware.
  - `sari/nodes/{node_id}/status`: Estado de presencia en red.
  - `sari/alerts`: Ingesta de detecciones de intrusos generadas por los modelos YOLO de las Jetsons.
- **Last Will and Testament (LWT)**: Si una Jetson sufre un corte de cable, apagón o interferencia, el broker publica inmediatamente su desconexión física.
- **Cliente Dual Resiliente (`jetson_telemetry.py`)**: Script optimizado para la Jetson con reconexión automática y conmutación transparente a fallback HTTP REST si la conexión MQTT se degrada.

---

### 3. 🤖 Bot Táctico y Alertas en Telegram
- **Notificaciones Inmediatas de Intrusión**: Despacho de alertas con fotografía de evidencia, nivel de confianza del modelo de visión, marca temporal y botones interactivos:
  - `🚨 Activar Sirena 30s`
  - `🔒 Bloquear Accesos`
  - `🔊 Silenciar Sirena`
- **Watchdog Anti-Sabotaje de Conexión**: Monitoreo continuo de señales de vida (Heartbeat). Si un nodo en línea deja de transmitir por más de 15 segundos o envía LWT, despacha una alerta crítica de posible sabotaje a Telegram.
- **Comandos Tácticos Bidireccionales**:
  - `/sirena`: Dispara la alarma sonora física del recinto.
  - `/silenciar`: Detiene inmediatamente la sirena.
  - `/bloquear`: Enclava magnéticamente todos los accesos perimetrales.
  - `/estado`: Retorna el estado consolidado de la infraestructura, base de datos y nodos activos.
  - `/fotos`: Solicita y envía al chat capturas actualizadas de todos los módulos Ojos activos.
  - `/foto <ID_MODULO>`: Solicita y envía la captura de una Jetson específica.
- **Seguridad Táctica**: Whitelist estricta mediante `TELEGRAM_ALLOWED_CHAT_IDS` para ignorar mensajes de usuarios ajenos al equipo de seguridad.

---

### 4. 🛡️ Motor de IA y Seguridad con NeMo Guardrails
- **Ejecución 100% Offline**: Políticas de seguridad estrictas sin salida a internet para evitar fugas de información táctica o planos perimetrales.
- **Validación de Prompts e Inyecciones**: Bloqueo de ataques de ingeniería social o intentos de evasión de restricciones operativas.
- **Herramientas Físicas Inmediatas**: Integración directa con herramientas tácticas (`activar_sirena`, `desactivar_sirena`, `cerrar_accesos`) invocadas automáticamente por el LLM ante solicitudes de emergencia.

---

## 🛠️ Requisitos del Sistema

- **Host (Servidor Central)**:
  - Linux (Ubuntu 22.04 LTS o superior recomendado).
  - [Docker](https://docs.docker.com/get-docker/) y [Docker Compose](https://docs.docker.com/compose/install/).
  - Puertos libres: `5173` (Frontend), `7000` (Backend API), `1883` (MQTT), `5000` (Sirena), `5433` (PostgreSQL).
- **Nodos Periféricos (Módulos Ojos)**:
  - NVIDIA Jetson Orin Nano / Nano / Xavier NX con JetPack.
  - Python 3.8+ con `paho-mqtt`, `psutil` y `requests`.

---

## ⚡ Guía Rápida de Despliegue

### 1. Clonar el repositorio y configurar variables de entorno
```bash
git clone git@github.com:suriel01/SARI_brain_agent_module.git
cd SARI_brain_agent_module
cp .env.example .env
```

Edita `.env` para ingresar tu token de Telegram y Chat ID:
```env
TELEGRAM_BOT_TOKEN=tu_token_de_bot
TELEGRAM_ALLOWED_CHAT_IDS=tu_chat_id
```

### 2. Levantar la infraestructura completa con Docker Compose
```bash
docker compose up -d --build
```

### 3. Verificar estado de los contenedores
```bash
docker compose ps
```
Deberás ver activos: `sari-ui`, `sari-backend`, `sari-mqtt`, `sari-sirena` y `sari_postgres`.

### 4. Acceder al SOC Dashboard
Abre tu navegador en:
👉 **[http://localhost:5173](http://localhost:5173)**

- **Usuario**: `admin`
- **Contraseña**: `sari_password`
- **PIN de Seguridad**: `1234`

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una suite completa de pruebas unitarias y de integración que validan el flujo MQTT, fallback HTTP, comandos de Telegram, watchdog de desconexión y base de datos:

```bash
docker exec -e PYTHONPATH=/app -t sari-backend pytest tests/ -v
```

Resultado esperado: **12 passed (100%)**.

---

## 📂 Estructura del Repositorio

```
SARI_brain_agent_module/
├── backend/
│   └── app/
│       ├── crud/              # Operaciones en base de datos PostgreSQL
│       ├── guardrails/        # Rieles de seguridad NeMo Guardrails
│       ├── models/            # Modelos SQLAlchemy (Users, Chats, EyeNodes, EventLogs)
│       ├── mqtt/              # Cliente asíncrono y handlers de eventos MQTT
│       ├── routers/           # Endpoints FastAPI (auth, chat, hardware, eyes, alerts)
│       ├── telegram/          # Servicio bot, webhook, watchdog y comandos tácticos
│       └── main.py            # Inicialización de servicios y ciclo de vida
├── sari-ui/                   # Frontend SOC Dashboard en React + TypeScript
│   └── src/
│       ├── components/        # Login, Dashboard, ChatPanel, EyesPanel, ControlPanel, UsersPanel
│       └── i18n/              # Soporte multilingüe (Español / English)
├── mosquitto/                 # Configuración y credenciales del broker MQTT
├── specs/                     # Especificaciones técnicas formales (001 a 005)
│   ├── 001-protocolo-seguridad.md
│   ├── 002-mqtt-wireless-telemetry.md
│   ├── 003-eyes-surveillance-module.md
│   ├── 004-telegram-tactical-integration.md
│   └── 005-hardware-tamper-autoprotection.md
├── doc/                       # Documentación de arquitectura, prompts y tareas
├── tests/                     # Suite de pruebas automatizadas (pytest)
├── sirena_service.py          # Microservicio emulador de sirena táctica física
├── jetson_telemetry.py        # Daemon dual MQTT/HTTP para nodos NVIDIA Jetson
├── sari-jetson.service        # Unidad systemd para despliegue en Jetsons
├── docker-compose.yml         # Orquestador multi-contenedor
└── README.md
```

---

## 📜 Licencia y Confidencialidad

Sistema de Respuesta Táctica Autónoma **SARI**. Desarrollado para operaciones de seguridad de alta criticidad. Todos los derechos reservados.
