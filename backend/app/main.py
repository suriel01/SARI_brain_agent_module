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

from pathlib import Path

from sqlalchemy import inspect, text

logger = logging.getLogger("sari_db")

# backend/migrations locally, /app/migrations in the image: always next to the `app` package.
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_LEGACY_POSTGRES_PATCHES = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_create_chats BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_delete_chats BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_rename_chats BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_control_hardware BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_manage_users BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS snapshot TEXT;",
)


def alembic_config():
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


def _adopt_legacy_schema(connection) -> None:
    """Brings a pre-Alembic database (built by ``create_all``) up to the baseline without touching data.

    Only additive statements: missing tables are created and missing columns added; nothing is
    dropped or altered.
    """
    if connection.dialect.name == "postgresql":
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    models.Base.metadata.create_all(bind=connection, checkfirst=True)
    if connection.dialect.name == "postgresql":
        for statement in _LEGACY_POSTGRES_PATCHES:
            connection.execute(text(statement))


def init_db(bind=None) -> None:
    """Applies the schema through Alembic.

    - Existing deployment (app tables but no ``alembic_version``): legacy additive patches once, then
      ``stamp head``. Data is never dropped or rewritten.
    - Otherwise (fresh or already versioned database): ``upgrade head``.
    """
    from alembic import command

    bind = bind if bind is not None else engine
    cfg = alembic_config()
    with bind.begin() as connection:
        cfg.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        app_tables = tables & set(models.Base.metadata.tables)
        if app_tables and "alembic_version" not in tables:
            logger.warning("Database has no alembic_version: adopting the existing schema and stamping head")
            _adopt_legacy_schema(connection)
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")


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
    # Logged only after the schema step and the seed queries actually succeeded (S15).
    from .adapters.composition import state
    state.add_log("🧠 Brain Module online & listening for YOLO vision node alerts.", level="INFO", camera_module="SYS_CORE")
    state.add_log("🔐 Database reachable; schema at the latest migration.", level="INFO", camera_module="SYS_CORE")

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
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from .routers.deps import authenticate_token

@app.websocket("/ws")
@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    # Browsers cannot set headers on a WebSocket handshake, so the JWT comes as ?token=.
    try:
        authenticate_token(websocket.query_params.get("token", ""))
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
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
