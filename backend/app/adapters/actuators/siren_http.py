"""SirenPort over the siren microservice HTTP API (`sirena_service.py`)."""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger("sari_hardware")

SIRENA_SERVICE_URL = os.environ.get("SIRENA_SERVICE_URL", "http://localhost:5000")


def siren_headers() -> dict:
    from ...config import get_settings

    return {"X-SARI-Siren-Token": get_settings().siren_token}


def call_siren_service(path: str, payload: Optional[dict]) -> tuple:
    """Calls the siren microservice. Returns (ok, reason); ok only on a 2xx answer."""
    try:
        kwargs = {"headers": siren_headers(), "timeout": 2.0}
        if payload is not None:
            kwargs["json"] = payload
        res = requests.post(f"{SIRENA_SERVICE_URL}{path}", **kwargs)
    except Exception as exc:
        logger.error("Siren service unreachable on %s: %s", path, exc)
        return False, "siren service unreachable"
    status = getattr(res, "status_code", None)
    if not isinstance(status, int) or not 200 <= status < 300:
        logger.error("Siren service answered %s on %s", status, path)
        return False, f"siren service answered HTTP {status}"
    return True, ""


class HttpSiren:
    def activate(self, duration) -> tuple:
        return call_siren_service("/api/alarma/activar", {"duracion": duration})

    def deactivate(self) -> tuple:
        return call_siren_service("/api/alarma/desactivar", None)

    def health(self) -> bool:
        """True when the siren service answers its health check (supervision heartbeat)."""
        try:
            res = requests.get(f"{SIRENA_SERVICE_URL}/health", timeout=2.0)
            return res.status_code == 200 and res.json().get("status") == "ok"
        except Exception as exc:
            logger.warning("Siren service health check failed: %s", exc)
            return False
