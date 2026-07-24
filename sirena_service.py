#!/usr/bin/env python3
"""
sirena_service.py — Microservicio HTTP minimalista para reproducir alertas sonoras.

Escucha en 127.0.0.1:5000 (solo accesible localmente).
Reproduce audio vía `spd-say` en las bocinas de la laptop.

Llamado por:
  - cerebro.py (activación automática ante intrusión)
  - mcp_server.py (activación manual desde Odysseus)
"""

import json
import subprocess
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 5000
BIND = "0.0.0.0"  # Escuchar en todas las interfaces para que Docker pueda llegar

# Control de la sirena activa
_sirena_activa = False
_sirena_lock = threading.Lock()


def _reproducir_alerta(duracion: int):
    """Reproduce la alerta sonora usando spd-say."""
    global _sirena_activa
    with _sirena_lock:
        if _sirena_activa:
            return  # Ya hay una sirena activa, no duplicar
        _sirena_activa = True

    try:
        mensaje = f"Alerta de seguridad SARI. Intrusión detectada. Sirena activa por {duracion} segundos."
        subprocess.Popen(
            ["spd-say", "-l", "es", "-r", "-30", mensaje],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"[SIRENA] 🚨 Alarma activada por {duracion} segundos.")

        # Programar la desactivación automática
        def _auto_desactivar():
            time.sleep(duracion)
            with _sirena_lock:
                global _sirena_activa
                _sirena_activa = False
            print("[SIRENA] ⏹️ Alarma finalizada automáticamente.")

        threading.Thread(target=_auto_desactivar, daemon=True).start()

    except FileNotFoundError:
        print("[SIRENA] ❌ Error: 'spd-say' no encontrado. Instálalo con: sudo apt install speech-dispatcher")
        with _sirena_lock:
            _sirena_activa = False
    except Exception as e:
        print(f"[SIRENA] ❌ Error al reproducir audio: {e}")
        with _sirena_lock:
            _sirena_activa = False


def _desactivar_alerta():
    """Desactiva la sirena y reproduce confirmación."""
    global _sirena_activa
    with _sirena_lock:
        _sirena_activa = False

    try:
        subprocess.Popen(
            ["spd-say", "-l", "es", "Sirena desactivada."],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("[SIRENA] 🔊 Sirena desactivada manualmente.")
    except Exception as e:
        print(f"[SIRENA] Error al confirmar desactivación: {e}")


class SirenaHTTPHandler(BaseHTTPRequestHandler):
    """Handler HTTP minimalista para el servicio de sirena."""

    def log_message(self, format, *args):
        """Silenciar los logs de acceso HTTP por defecto."""
        pass

    def _send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "service": "sirena_service",
                "sirena_activa": _sirena_activa
            })
        else:
            self._send_json(404, {"error": "Ruta no encontrada"})

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (json.JSONDecodeError, ValueError):
            payload = {}

        if self.path == "/api/alarma/activar":
            duracion = payload.get("duracion", 30)
            _reproducir_alerta(duracion)
            self._send_json(200, {
                "status": "success",
                "message": f"Alarma activada por {duracion}s"
            })

        elif self.path == "/api/alarma/desactivar":
            _desactivar_alerta()
            self._send_json(200, {
                "status": "success",
                "message": "Alarma desactivada"
            })

        else:
            self._send_json(404, {"error": "Ruta no encontrada"})


def iniciar_servicio():
    """Punto de entrada principal del servicio de sirena."""
    server = HTTPServer((BIND, PORT), SirenaHTTPHandler)
    print(f"[SIRENA] Servicio de audio escuchando en http://{BIND}:{PORT}")
    print(f"[SIRENA] Health check: http://localhost:{PORT}/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SIRENA] Servicio detenido.")
        server.server_close()


if __name__ == "__main__":
    iniciar_servicio()
