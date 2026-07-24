# 🛡️ SARI Brain Agent — Sistema Autónomo de Respuesta a Intrusiones

**SARI (Sistema Autónomo de Respuesta a Intrusiones)** es una plataforma de seguridad perimetral autónoma de nivel empresarial que combina Inteligencia Artificial local, visión por computadora en tiempo real (**NVIDIA Jetson con YOLO26n**), control de hardware físico y una consola gráfica de Centro de Operaciones de Seguridad (SOC).

---

## 🚀 Características Principales

- **Consola Táctica SOC (Frontend React + Vite)**:
  - Interfaz gráfica profesional en modo oscuro con efectos CRT Scanlines.
  - mapa de radar animado para monitoreo de perímetro.
  - Sintetizador de alarma sonora en tiempo real mediante Web Audio API en el navegador.
  - Hilos de chat compartidos en tiempo real entre administradores y monitores.

- **Arquitectura Escalable MVC (FastAPI + PostgreSQL 15)**:
  - Backend modularizado en routers (`auth`, `chat`, `users`, `hardware`, `alerts`).
  - Base de datos relacional PostgreSQL con persistencia permanente de hilos de conversación, historial de chat y cuentas de usuario.

- **Matriz de Permisos Granulares (RBAC)**:
  - Creación y eliminación de operadores con checkboxes de permisos individuales (`can_create_chats`, `can_delete_chats`, `can_rename_chats`, `can_control_hardware`, `can_manage_users`).
  - Protección de acciones sensibles (Creación y eliminación de chats) mediante **PIN de Seguridad (`1234`)**.
  - Eliminación de operadores directamente desde la consola de administración.

- **Integración con Nodos de Visión Jetson (YOLO26n)**:
  - Endpoint REST/MCP automatizado (`POST /api/alerts/event`).
  - Al recibir una detección de cámara, SARI genera automáticamente un **hilo de evidencia de chat** con los detalles del dispositivo, nivel de confianza y activa la sirena perimetral de forma autónoma.

- **Microservicio de Hardware Táctico (`sirena_service.py`)**:
  - Control de sirenas sonoras físicas y bloqueo perimetral de accesos.

---

## 🛠️ Requisitos Previos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

---

## ⚡ Inicio Rápido (Despliegue con Docker)

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/suriel01/SARI_brain_agent.git
   cd SARI_brain_agent
   ```

2. Levantar la infraestructura completa con Docker Compose:
   ```bash
   docker compose up -d --build
   ```

3. Abrir la interfaz gráfica en el navegador:
   👉 **[http://localhost:5173](http://localhost:5173)**

### 🔑 Credenciales Iniciales por Defecto

- **Usuario Administrador**: `admin`
- **Contraseña**: `sari_password`
- **PIN de Seguridad para Hilos**: `1234`

---

## 📡 Integración con Módulos Jetson YOLO26n

Los nodos de visión por computadora pueden enviar eventos de alerta en tiempo real realizando peticiones HTTP POST al backend:

```bash
curl -X POST http://localhost:7000/api/alerts/event \
  -H "Content-Type: application/json" \
  -d '{
    "module_name": "Jetson-PTZ-Perimetro-Sur",
    "event": "Intrusión de vehículo no autorizado",
    "confidence": 0.98,
    "auto_siren": true
  }'
```

**Respuesta Automática del Sistema**:
- Creación de un hilo de evidencia en la BD titulado `🚨 [EVIDENCIA] Jetson-PTZ-Perimetro-Sur (HH:MM:SS)`.
- Activación de la sirena perimetral.
- Disparo del audio táctico en el navegador web del operador.

---

## 📂 Estructura del Proyecto

```
SARI_brain_agent/
├── backend/
│   ├── app/
│   │   ├── crud/           # Lógica de operaciones en PostgreSQL
│   │   ├── models/         # Modelos SQLAlchemy (User, ChatThread, ChatMessage)
│   │   ├── routers/        # Rutas de la API (auth, chat, users, hardware, alerts)
│   │   ├── schemas/        # Esquemas de validación Pydantic
│   │   ├── database.py     # Conexión a PostgreSQL
│   │   └── main.py         # Punto de entrada FastAPI con auto-migración
│   └── Dockerfile.backend
├── sari-ui/                # Frontend React + TypeScript
│   ├── src/
│   │   ├── components/     # Componentes (Dashboard, ChatPanel, AdminPanel, HardwarePanel, RadarMap)
│   │   └── index.css       # Estilos globales SOC + CRT Scanlines
│   └── Dockerfile
├── sirena_service.py       # Microservicio HTTP de sirenas sonoras
├── Dockerfile.sirena
├── docker-compose.yml      # Orquestador Docker (PostgreSQL, Backend, UI, Sirena)
├── AGENTS.md               # Especificación y directivas del Agente IA
└── README.md
```

---

## 📜 Licencia

Desarrollado para la infraestructura de seguridad autónoma **SARI**. Todos los derechos reservados.
