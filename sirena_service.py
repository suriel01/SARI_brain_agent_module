#!/usr/bin/env python3
"""
sirena_service.py — Microservicio HTTP de Alarma Física & Sirena de Emergencia Real SARI.

Escucha en 0.0.0.0:5000 dentro de la red interna de Docker (no se publica en el host).
Toda orden POST requiere la cabecera X-SARI-Siren-Token igual a SARI_SIREN_TOKEN.
Genera y reproduce un tono físico real de sirena de emergencia (onda modulada de alta intensidad) por altavoces.
"""

import hmac
import os
import sys
import wave
import math
import struct
import json
import subprocess
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 5000
BIND = "0.0.0.0"
WAV_PATH = "/tmp/sirena_emergencia.wav"
MAX_DURATION_SECONDS = 300
TOKEN_HEADER = "X-SARI-Siren-Token"  # noqa: S105 - header name, not a secret
SIREN_TOKEN = os.environ.get("SARI_SIREN_TOKEN", "").strip()

_sirena_activa = False
_sirena_lock = threading.Lock()
_active_processes = []


def _generar_wav_sirena_si_no_existe():
    """Genera un archivo WAV de sirena de emergencia real (barrido de frecuencia 600Hz-1600Hz)."""
    if os.path.exists(WAV_PATH):
        return

    sample_rate = 22050
    duration = 2.0  # Ciclo de 2 segundos de oscilación aguda
    num_samples = int(sample_rate * duration)

    try:
        with wave.open(WAV_PATH, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            phase = 0.0
            for i in range(num_samples):
                t = i / sample_rate
                # Sweep estilo alarma de pánico (frecuencia entre 600Hz y 1600Hz)
                sweep = math.sin(2 * math.pi * 1.5 * t)
                freq = 1100 + 500 * sweep
                phase += 2 * math.pi * freq / sample_rate

                # Tono con armónicos para sonar metálico/agudo como sirena real
                sample = int(26000 * math.sin(phase) + 5000 * math.sin(2 * phase))
                sample = max(-32767, min(32767, sample))
                wav_file.writeframes(struct.pack('<h', sample))
        print(f"[SIRENA] Tono de sirena real generado exitosamente en {WAV_PATH}")
    except Exception as e:
        print(f"[SIRENA] Error generando WAV de sirena: {e}")


def _detener_procesos_audio():
    global _active_processes
    with _sirena_lock:
        for proc in _active_processes:
            try:
                proc.terminate()
                proc.kill()
            except Exception:
                pass
        _active_processes.clear()


def _play_siren_cycle():
    """Ejecuta una reproducción del tono WAV con aplay o paplay."""
    _generar_wav_sirena_si_no_existe()
    for player in ["aplay", "paplay"]:
        try:
            proc = subprocess.Popen([player, WAV_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with _sirena_lock:
                _active_processes.append(proc)
            proc.wait()
            return
        except Exception:
            continue


def _reproducir_alerta(duracion: int):
    """Reproduce el tono real de sirena de emergencia en bucle continuo durante la duración especificada."""
    global _sirena_activa
    with _sirena_lock:
        _sirena_activa = True

    _detener_procesos_audio()
    print(f"[SIRENA] 🚨 ALARMA DE SIRENA REAL ACTIVADA por {duracion} segundos.")

    def _loop_sirena():
        global _sirena_activa
        t_start = time.time()

        while True:
            with _sirena_lock:
                if not _sirena_activa or (time.time() - t_start >= duracion):
                    break

            # Reproducir un ciclo del sonido de la sirena
            _play_siren_cycle()

        with _sirena_lock:
            _sirena_activa = False
        print("[SIRENA] ⏹️ Alarma de sirena finalizada.")

    threading.Thread(target=_loop_sirena, daemon=True).start()


def _desactivar_alerta():
    """Desactiva la sirena física inmediatamente."""
    global _sirena_activa
    with _sirena_lock:
        _sirena_activa = False

    _detener_procesos_audio()
    print("[SIRENA] 🔊 Sirena desactivada manualmente.")


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

    def _authorized(self) -> bool:
        supplied = self.headers.get(TOKEN_HEADER, "")
        return bool(SIREN_TOKEN) and hmac.compare_digest(supplied.encode(), SIREN_TOKEN.encode())

    def do_POST(self):
        if not self._authorized():
            self._send_json(401, {"error": "No autorizado"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (json.JSONDecodeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "El cuerpo debe ser un objeto JSON"})
            return

        if self.path == "/api/alarma/activar":
            raw = payload.get("duracion", 30)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw <= 0:
                self._send_json(400, {"error": "duracion debe ser un número positivo de segundos"})
                return
            duracion = min(int(raw), MAX_DURATION_SECONDS)
            if duracion <= 0:
                self._send_json(400, {"error": "duracion debe ser un número positivo de segundos"})
                return
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
    if not SIREN_TOKEN:
        print("[SIRENA] SARI_SIREN_TOKEN no está definido; el servicio no arranca.")
        sys.exit(1)
    _generar_wav_sirena_si_no_existe()
    server = HTTPServer((BIND, PORT), SirenaHTTPHandler)
    print(f"[SIRENA] Servicio de audio escuchando en http://{BIND}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SIRENA] Servicio detenido.")
        server.server_close()


if __name__ == "__main__":
    iniciar_servicio()
