import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
from .config import ConfigError, KNOWN_INSECURE_VALUES, get_settings
from .database import engine, SessionLocal

# Fail closed: refuse to start without the required security settings.
get_settings()
from .models import models
from .schemas import schemas
from .crud import crud
from .routers import auth, chat, hardware, users, alerts, eyes

from sqlalchemy import text


def init_db() -> None:
    """Create extensions, tables and legacy column patches. Postgres-only statements are skipped elsewhere."""
    is_postgres = engine.dialect.name == "postgresql"
    if is_postgres:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

    models.Base.metadata.create_all(bind=engine)

    if is_postgres:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_create_chats BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_delete_chats BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_rename_chats BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_control_hardware BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_manage_users BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS snapshot TEXT;"))
            conn.commit()


app = FastAPI(title="SARI Brain Agent Backend")

_cors_raw = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
CORS_ORIGINS = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]
if CORS_ORIGINS == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def seed_initial_data() -> None:
    """Seed the bootstrap admin, default thread and default eye node. Admin password comes from SARI_ADMIN_PASSWORD."""
    db = SessionLocal()
    try:
        admin = crud.get_user_by_username(db, "admin")
        if not admin:
            bootstrap_password = os.environ.get("SARI_ADMIN_PASSWORD", "").strip()
            if not bootstrap_password or bootstrap_password in KNOWN_INSECURE_VALUES:
                raise ConfigError("SARI_ADMIN_PASSWORD is required to create the initial admin user")
            admin_user = schemas.UserCreate(
                username="admin",
                password=bootstrap_password,
                role="admin",
                clearance_level=5
            )
            admin = crud.create_user(db, admin_user)
            print("Admin user created successfully")
        
        # Crear hilo por defecto si no existen
        threads = crud.get_user_threads(db)
        if not threads:
            t = crud.create_thread(db, user_id=admin.id, title="Centro de Comando SARI")
            crud.add_message(db, t.id, role="agent", content="🛡️ Sistema Autónomo de Respuesta a Intrusiones (SARI) activo y escuchando comandos.")

        # Seed default Jetson-PTZ_1 Eye node
        default_eye = db.query(models.EyeNode).filter(models.EyeNode.node_id == "Jetson-PTZ_1").first()
        if not default_eye:
            eye1 = models.EyeNode(
                node_id="Jetson-PTZ_1",
                name="Jetson Orin Nano (PTZ 1)",
                ip="192.168.55.1",
                stream_url="http://192.168.55.1:8080/mjpeg",
                yolo_threshold=0.70,
                is_active=True
            )
            db.add(eye1)
            db.commit()
            print("Default Jetson-PTZ_1 eye node registered")
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    init_db()
    seed_initial_data()

    # Iniciar cliente MQTT en segundo plano
    try:
        from .mqtt.client import start_mqtt_client
        start_mqtt_client()
    except Exception as e:
        print(f"[MQTT] Error starting background client: {e}")

    # Iniciar bot y watchdog de Telegram en segundo plano
    try:
        from .telegram.bot import start_telegram_bot
        from .telegram.watchdog import start_watchdog
        start_telegram_bot()
        start_watchdog()
    except Exception as e:
        print(f"[Telegram] Error starting bot/watchdog: {e}")

@app.on_event("shutdown")
def shutdown_event():
    try:
        from .mqtt.client import stop_mqtt_client
        stop_mqtt_client()
    except Exception as e:
        print(f"[MQTT] Error stopping background client: {e}")

    try:
        from .telegram.bot import stop_telegram_bot
        from .telegram.watchdog import stop_watchdog
        stop_telegram_bot()
        stop_watchdog()
    except Exception as e:
        print(f"[Telegram] Error stopping bot/watchdog: {e}")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(alerts.router, prefix="/api/alert", tags=["alerts"])
app.include_router(alerts.router, prefix="/api", tags=["alerts"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(hardware.router, prefix="/api/hardware", tags=["hardware"])
app.include_router(eyes.router, prefix="/api/eyes", tags=["eyes"])
app.include_router(hardware.router, prefix="/api", tags=["hardware"])

from .ws import manager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

@app.websocket("/ws")
@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def root():
    return {"status": "SARI Brain Agent API Online"}

@app.get("/health")
def health():
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
    }
