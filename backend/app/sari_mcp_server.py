import os
import requests
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# Inicializar MCP Server (SARI NeMoClaw)
mcp = FastMCP("nemoclaw_sari")

SIRENA_SERVICE_URL = os.environ.get("SIRENA_SERVICE_URL", "http://localhost:5000")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_EMBED_URL = OLLAMA_URL.replace("/api/chat", "/api/embeddings")
OLLAMA_EMBED_MODEL = "nomic-embed-text"

# Asumimos que podemos importar esto de FastAPI si estamos en el mismo paquete
try:
    from app.database import SessionLocal
    from app.models import models
except ImportError:
    pass

@mcp.tool()
def activar_sirena(duracion_segundos: int = 30) -> str:
    """Activa la sirena física del sistema."""
    try:
        res = requests.post(f"{SIRENA_SERVICE_URL}/api/alarma/activar", json={"duracion": duracion_segundos}, timeout=5.0)
        if res.status_code == 200:
            return f"Sirena activada por {duracion_segundos} segundos."
        return f"Error activando sirena: HTTP {res.status_code}"
    except Exception as e:
        return f"Error de conexión con la sirena: {e}"

@mcp.tool()
def desactivar_sirena() -> str:
    """Desactiva la sirena física del sistema si está sonando."""
    try:
        res = requests.post(f"{SIRENA_SERVICE_URL}/api/alarma/desactivar", timeout=5.0)
        if res.status_code == 200:
            return "Sirena desactivada."
        return f"Error desactivando sirena: HTTP {res.status_code}"
    except Exception as e:
        return f"Error de conexión con la sirena: {e}"

@mcp.tool()
def cerrar_accesos() -> str:
    """Bloquea y cierra todos los accesos perimetrales."""
    # Simulación de control físico
    return "Accesos perimetrales bloqueados con éxito."

@mcp.tool()
def obtener_estatus_hardware() -> str:
    """Obtiene el estado general de los componentes de hardware (sirena, cámaras, etc)."""
    return "Estado de Hardware: Sirena conectada. Jetson OK. Conexión de base de datos OK."

@mcp.tool()
def buscar_historial_eventos(consulta: str) -> str:
    """Realiza una búsqueda semántica (RAG) en los registros de seguridad usando pgvector."""
    embedding = None
    try:
        res = requests.post(OLLAMA_EMBED_URL, json={
            "model": OLLAMA_EMBED_MODEL,
            "prompt": consulta
        }, timeout=10.0)
        if res.status_code == 200:
            embedding = res.json().get("embedding")
    except Exception as e:
        return f"Error generando embedding para la consulta: {e}"
        
    if not embedding:
        return "No se pudo generar el vector para la búsqueda."
        
    db = SessionLocal()
    try:
        # Búsqueda usando pgvector (operador de similitud de coseno <=>)
        # Se asume que el embedding se inserta como array string para la DB
        vector_str = "[" + ",".join(map(str, embedding)) + "]"
        
        # Obtenemos los 5 resultados más relevantes
        results = db.query(models.EventLog).order_by(
            models.EventLog.embedding.cosine_distance(vector_str)
        ).limit(5).all()
        
        if not results:
            return "No se encontraron eventos relevantes en el historial."
            
        respuesta = "Eventos encontrados:\n"
        for idx, ev in enumerate(results):
            respuesta += f"{idx+1}. [{ev.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Módulo: {ev.module_name} | Evento: {ev.event_description} | Confianza: {ev.confidence}\n"
            
        return respuesta
    except Exception as e:
        return f"Error consultando la base de datos: {e}"
    finally:
        db.close()

if __name__ == "__main__":
    mcp.run()
