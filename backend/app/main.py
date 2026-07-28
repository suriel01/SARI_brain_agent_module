from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, SessionLocal
from .models import models
from .schemas import schemas
from .crud import crud
from .routers import auth, chat, hardware, users, alerts

from sqlalchemy import text

# Habilitar extensión pgvector ANTES de crear tablas
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    conn.commit()

# Crear tablas
models.Base.metadata.create_all(bind=engine)

# Auto-migration de columnas para la tabla users DESPUES de crear tablas
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_create_chats BOOLEAN DEFAULT FALSE;"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_delete_chats BOOLEAN DEFAULT FALSE;"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_rename_chats BOOLEAN DEFAULT FALSE;"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_control_hardware BOOLEAN DEFAULT FALSE;"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_manage_users BOOLEAN DEFAULT FALSE;"))
    conn.commit()

app = FastAPI(title="SARI Brain Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed Admin User y Hilo Inicial
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        admin = crud.get_user_by_username(db, "admin")
        if not admin:
            admin_user = schemas.UserCreate(
                username="admin", 
                password="sari_password", 
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
    finally:
        db.close()

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(alerts.router, prefix="/api/alert", tags=["alerts"])
app.include_router(hardware.router, prefix="/api/hardware", tags=["hardware"])
app.include_router(hardware.router, prefix="/api", tags=["hardware"])

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

@app.websocket("/ws")
@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass

@app.get("/")
def root():
    return {"status": "SARI Brain Agent API Online"}
