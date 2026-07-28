#!/usr/bin/env python3
"""
sirena_service.py — Microservicio HTTP de Alarma Física & Respuesta Auditiva SARI.

Escucha en 0.0.0.0:5000.
Reproduce alertas sonoras físicas de sirena y voz sintética a través de los altavoces.
"""

import os
import math
import struct
import wave
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

WAV_PATH = "/tmp/sirena_alarm.wav"

def _generar_wav_sirena():
    """Genera un archivo WAV de tono de alarma física de alta frecuencia (2 tonos)."""
    try:
        sample_rate = 22050
        duracion_sec = 4
        num_samples = sample_rate * duracion_sec
        with wave.open(WAV_PATH, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            
            for i in range(num_samples):
                t = i / sample_rate
                # Modulación de frecuencia de sirena policial 700Hz - 1300Hz
                freq = 1000 + 400 * math.sin(2 * math.pi * 3 * t)
                value = int(22000 * math.sin(2 * math.pi * freq * t))
                data = struct.pack('<h', value)
                wav_file.writeframesraw(data)
    except Exception as e:
        print(f"[SIRENA] Error al generar WAV de sirena: {e}")

# Generar archivo de tono al iniciar
_generar_wav_sirena()

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
    """Reproduce la alerta sonora física de sirena y voz sintética."""
    global _sirena_activa
    with _sirena_lock:
        _sirena_activa = True

    _detener_procesos_audio()
    print(f"[SIRENA] 🚨 ALARMA FÍSICA ACTIVADA por {duracion} segundos.")

    def _loop_sirena():
        t_start = time.time()
        
        # Voz de anuncio inicial en hilo secundario
        mensaje_voz = f"Alerta de seguridad SARI. Intrusión detectada. Sirena activa por {duracion} segundos."
        threading.Thread(target=lambda: _play_audio_command(["espeak-ng", "-v", "es", "-s", "150", mensaje_voz]), daemon=True).start()

        # Bucle de reproduccion de tono de sirena mientras este activa
        while True:
            with _sirena_lock:
                if not _sirena_activa or (time.time() - t_start >= duracion):
                    break

            # Probar paplay (PulseAudio) primero, luego aplay (ALSA)
            if os.path.exists(WAV_PATH):
                _play_audio_command(["paplay", WAV_PATH])
            else:
                time.sleep(1)

        with _sirena_lock:
            _sirena_activa = False
        print("[SIRENA] ⏹️ Alarma física finalizada automáticamente.")

    threading.Thread(target=_loop_sirena, daemon=True).start()


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
