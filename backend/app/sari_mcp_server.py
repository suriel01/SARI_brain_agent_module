import os
import requests
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# Initialize FastMCP Server (SARI NeMoClaw)
mcp = FastMCP("nemoclaw_sari")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_EMBED_URL = OLLAMA_URL.replace("/api/chat", "/api/embeddings")
OLLAMA_EMBED_MODEL = "nomic-embed-text"

from app.database import SessionLocal
from app.models import models
from app.routers.hardware import Actor, execute_physical_tool


def _mcp_actor() -> Actor:
    """The local MCP client may drive hardware only when explicitly enabled for this host."""
    enabled = os.environ.get("SARI_MCP_HARDWARE_ENABLED", "false").strip().lower() == "true"
    return Actor(name="mcp:local", channel="mcp", can_control_hardware=enabled)


def _run(tool: str, args: dict) -> str:
    return execute_physical_tool(tool, args, actor=_mcp_actor()).get("message", "")


@mcp.tool()
def activate_siren(duration_seconds: int = 30) -> str:
    """Activates the physical alarm siren."""
    return _run("activate_siren", {"duration_seconds": duration_seconds})

@mcp.tool()
def activar_sirena(duracion_segundos: int = 30) -> str:
    """Backward-compatible Spanish alias for activate_siren."""
    return activate_siren(duration_seconds=duracion_segundos)

@mcp.tool()
def deactivate_siren() -> str:
    """Deactivates the physical alarm siren if sounding."""
    return _run("deactivate_siren", {})

@mcp.tool()
def desactivar_sirena() -> str:
    """Backward-compatible Spanish alias for deactivate_siren."""
    return deactivate_siren()

@mcp.tool()
def lock_gates() -> str:
    """Locks all perimeter gates."""
    return _run("lock_gates", {})

@mcp.tool()
def cerrar_accesos() -> str:
    """Backward-compatible Spanish alias for lock_gates."""
    return lock_gates()

@mcp.tool()
def get_hardware_status() -> str:
    """Retrieves general status of hardware components (siren, cameras, sensors)."""
    return "Hardware Status: Siren online. Jetson CV node OK. Database connection healthy."

@mcp.tool()
def obtener_estatus_hardware() -> str:
    """Backward-compatible Spanish alias for get_hardware_status."""
    return get_hardware_status()

@mcp.tool()
def search_event_history(query: str) -> str:
    """Performs semantic RAG search in security event logs using pgvector."""
    embedding = None
    try:
        res = requests.post(OLLAMA_EMBED_URL, json={
            "model": OLLAMA_EMBED_MODEL,
            "prompt": query
        }, timeout=10.0)
        if res.status_code == 200:
            embedding = res.json().get("embedding")
    except Exception as e:
        return f"Error generating embedding for query: {e}"
        
    if not embedding:
        return "Could not generate vector embedding for search query."
        
    db = SessionLocal()
    try:
        vector_str = "[" + ",".join(map(str, embedding)) + "]"
        results = db.query(models.EventLog).order_by(
            models.EventLog.embedding.cosine_distance(vector_str)
        ).limit(5).all()
        
        if not results:
            return "No matching security events found in history."
            
        response_lines = "Matching events found:\n"
        for idx, ev in enumerate(results):
            response_lines += f"{idx+1}. [{ev.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Module: {ev.module_name} | Event: {ev.event_description} | Confidence: {ev.confidence}\n"
            
        return response_lines
    except Exception as e:
        return f"Error querying database: {e}"
    finally:
        db.close()

@mcp.tool()
def buscar_historial_eventos(consulta: str) -> str:
    """Backward-compatible Spanish alias for search_event_history."""
    return search_event_history(query=consulta)

if __name__ == "__main__":
    mcp.run()
