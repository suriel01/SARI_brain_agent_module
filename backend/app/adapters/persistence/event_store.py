"""Stores detections in `event_logs` with their RAG embedding (Ollama, best effort)."""
import logging
import os

import requests

from ...database import SessionLocal
from ...models import models

logger = logging.getLogger("sari_alerts")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_EMBED_URL = OLLAMA_URL.replace("/api/chat", "/api/embeddings")
OLLAMA_EMBED_MODEL = "nomic-embed-text"


def save_event_and_embedding(module_name: str, event_desc: str, confidence: float):
    """Stores the detection in event_logs with its RAG embedding (best effort)."""
    embedding = None
    try:
        res = requests.post(OLLAMA_EMBED_URL, json={"model": OLLAMA_EMBED_MODEL, "prompt": f"[{module_name}] {event_desc}"}, timeout=10.0)
        if res.status_code == 200:
            embedding = res.json().get("embedding")
    except Exception as e:
        logger.warning("Error generating embedding: %s", e)

    db = SessionLocal()
    try:
        db.add(models.EventLog(module_name=module_name, event_description=event_desc, confidence=confidence, embedding=embedding))
        db.commit()
    except Exception as e:
        logger.error("Error storing event: %s", e)
        db.rollback()
    finally:
        db.close()
