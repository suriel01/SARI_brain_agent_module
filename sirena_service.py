#!/usr/bin/env python3
"""
sirena_service.py — Microservicio HTTP de Alarma Física & Respuesta Auditiva SARI.

Escucha en 0.0.0.0:5000.
Reproduce alertas de voz sintética a través de los altavoces mediante espeak-ng/spd-say.
"""

import json
import subprocess
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 5000
BIND = "0.0.0.0"

_sirena_activa = False
_sirena_lock = threading.Lock()
_active_processes = []


def _detener_procesos_audio():
    global _active_processes
    with _sirena_lock:
        for proc in _active_processes:
            try:
                proc.terminate()
            except Exception:
                pass
        _active_processes.clear()


def _play_audio_command(cmd_list):
    try:
        proc = subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with _sirena_lock:
            _active_processes.append(proc)
        proc.wait()
    except Exception as e:
        print(f"[SIRENA] Error ejecutando comando de audio {cmd_list[0]}: {e}")


def _reproducir_alerta(duracion: int):
    """Reproduce la alerta sonora usando el sintetizador de voz (espeak-ng/spd-say)."""
    global _sirena_activa
    with _sirena_lock:
        _sirena_activa = True

    _detener_procesos_audio()
    print(f"[SIRENA] 🚨 Alarma activada por {duracion} segundos.")

    def _loop_anuncio():
        t_start = time.time()
        mensaje = f"Alerta de seguridad SARI. Intrusión detectada. Sirena activa por {duracion} segundos."
        
        while True:
            with _sirena_lock:
                if not _sirena_activa or (time.time() - t_start >= duracion):
                    break
            
            # Anuncio de voz
            _play_audio_command(["espeak-ng", "-v", "es", "-s", "145", mensaje])
            time.sleep(1)

        with _sirena_lock:
            _sirena_activa = False
        print("[SIRENA] ⏹️ Alarma finalizada automáticamente.")

    threading.Thread(target=_loop_anuncio, daemon=True).start()


def _desactivar_alerta():
    """Desactiva la sirena física inmediatamente."""
    global _sirena_activa
    with _sirena_lock:
        _sirena_activa = False
    
    _detener_procesos_audio()
    print("[SIRENA] 🔊 Sirena desactivada manualmente.")
    threading.Thread(target=lambda: _play_audio_command(["espeak-ng", "-v", "es", "Sirena desactivada."]), daemon=True).start()


class SirenaHTTPHandler(BaseHTTPRequestHandler):
    """Handler HTTP para el servicio de sirena."""

    def log_message(self, format, *args):
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
                "message": f"Alarma activada por {duracion}s",
                "sirena_activa": True
            })

        elif self.path == "/api/alarma/desactivar":
            _desactivar_alerta()
            self._send_json(200, {
                "status": "success",
                "message": "Alarma desactivada",
                "sirena_activa": False
            })

        else:
            self._send_json(404, {"error": "Ruta no encontrada"})


def iniciar_servicio():
    server = HTTPServer((BIND, PORT), SirenaHTTPHandler)
    print(f"[SIRENA] Servicio de audio escuchando en http://{BIND}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SIRENA] Servicio detenido.")
        server.server_close()


if __name__ == "__main__":
    iniciar_servicio()
