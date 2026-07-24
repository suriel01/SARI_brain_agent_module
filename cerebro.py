#!/usr/bin/env python3
"""
cerebro.py — Módulo Cerebro de SARI.

Punto de entrada principal del sistema de seguridad perimetral.
Responsabilidades:
  1. Arrancar sirena_service.py como subproceso automático.
  2. Servidor WebSocket (puerto 8765) para recibir telemetría de la Jetson.
  3. Activar la sirena automáticamente cuando la Jetson reporta intrusión.

Uso:
  python3 cerebro.py
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time

import requests
import websockets

# =====================================================================
# CONFIGURACIÓN
# =====================================================================
PORT_WS = 8765
SIRENA_SERVICE_URL = "http://localhost:5000"

# Control de alertas
clientes_conectados = set()
estado_alertas = {
    "ultima_alerta": 0,
    "cooldown_alerta": 30  # segundos entre alertas
}

# Referencia al subproceso de sirena_service
_sirena_process = None


# =====================================================================
# ARRANQUE AUTOMÁTICO DE SIRENA SERVICE
# =====================================================================
def _iniciar_sirena_service():
    """Arranca sirena_service.py como subproceso en segundo plano."""
    global _sirena_process

    script_dir = os.path.dirname(os.path.abspath(__file__))
    sirena_path = os.path.join(script_dir, "sirena_service.py")

    if not os.path.exists(sirena_path):
        print(f"[CEREBRO] ❌ No se encontró {sirena_path}")
        sys.exit(1)

    # Usar el mismo intérprete de Python que está ejecutando cerebro.py
    python_bin = sys.executable

    print(f"[CEREBRO] Arrancando sirena_service.py...")
    _sirena_process = subprocess.Popen(
        [python_bin, sirena_path]
    )

    # Esperar un momento y verificar que arrancó correctamente
    time.sleep(1)
    if _sirena_process.poll() is not None:
        print("[CEREBRO] ❌ sirena_service.py falló al arrancar.")
        sys.exit(1)

    # Verificar health check
    try:
        resp = requests.get(f"{SIRENA_SERVICE_URL}/health", timeout=2)
        if resp.status_code == 200:
            print("[CEREBRO] ✅ sirena_service.py arrancado correctamente.")
        else:
            print(f"[CEREBRO] ⚠️ sirena_service.py respondió con HTTP {resp.status_code}")
    except requests.ConnectionError:
        print("[CEREBRO] ⚠️ sirena_service.py no respondió al health check. Continuando de todas formas...")


def _detener_sirena_service():
    """Detiene el subproceso de sirena_service."""
    global _sirena_process
    if _sirena_process and _sirena_process.poll() is None:
        print("[CEREBRO] Deteniendo sirena_service.py...")
        _sirena_process.terminate()
        try:
            _sirena_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _sirena_process.kill()
        print("[CEREBRO] sirena_service.py detenido.")


# =====================================================================
# ACTIVACIÓN DE SIRENA (LLAMADA DIRECTA A SIRENA_SERVICE)
# =====================================================================
def activar_sirena(duracion: int = 30):
    """Envía comando HTTP a sirena_service.py para activar la alarma."""
    try:
        resp = requests.post(
            f"{SIRENA_SERVICE_URL}/api/alarma/activar",
            json={"duracion": duracion},
            timeout=3
        )
        if resp.status_code == 200:
            print(f"[CEREBRO] 🚨 Sirena activada por {duracion}s")
        else:
            print(f"[CEREBRO] ⚠️ Error activando sirena: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[CEREBRO] ❌ No se pudo contactar a sirena_service: {e}")


# =====================================================================
# WEBSOCKET SERVER: RECIBE LA TELEMETRÍA DE LA JETSON
# =====================================================================
async def manejar_cliente(websocket, path=None):
    """Maneja la conexión WebSocket con una cámara Jetson."""
    print(f"[CEREBRO] Conexión WebSocket establecida desde Jetson: {websocket.remote_address}")
    clientes_conectados.add(websocket)

    try:
        async for mensaje in websocket:
            try:
                datos = json.loads(mensaje)
                tipo = datos.get("tipo")

                if tipo == "telemetria":
                    detecciones = datos.get("detecciones", [])
                    camara = datos.get("camara_id", "desconocida")
                    print(f"[{time.strftime('%H:%M:%S')}] Telemetría de {camara}: {len(detecciones)} personas.")

                    # Activación automática: 3 o más personas detectadas
                    if len(detecciones) >= 3:
                        ahora = time.time()
                        if ahora - estado_alertas["ultima_alerta"] > estado_alertas["cooldown_alerta"]:
                            estado_alertas["ultima_alerta"] = ahora
                            print(f"[CEREBRO] ⚠️ INTRUSIÓN DETECTADA en {camara}: {len(detecciones)} personas.")
                            activar_sirena(duracion=30)
                            # Notificar a NeMoClaw
                            try:
                                requests.post("http://localhost:7000/api/alert", json={"source": "Jetson", "camera": camara, "event": "intrusión_detectada", "count": len(detecciones), "duration_seconds": 30}, timeout=2.0)
                            except Exception:
                                pass

                elif tipo == "alerta":
                    camara = datos.get("camara_id", "desconocida")
                    razon = datos.get("razon", "sin especificar")
                    tiempo = datos.get("tiempo_detectado", 0)
                    print(f"[{time.strftime('%H:%M:%S')}] ALERTA CRÍTICA de {camara}: {razon}")

                    ahora = time.time()
                    if ahora - estado_alertas["ultima_alerta"] > estado_alertas["cooldown_alerta"]:
                        estado_alertas["ultima_alerta"] = ahora
                        print(f"[CEREBRO] 🚨 INTRUSIÓN PROLONGADA en {camara}: {tiempo}s - {razon}")
                        activar_sirena(duracion=60)
                        # Notificar a NeMoClaw
                        try:
                            requests.post("http://localhost:7000/api/alert", json={"source": "Jetson", "camera": camara, "event": "intrusión_prolongada", "count": 1, "duration_seconds": 60}, timeout=2.0)
                        except Exception:
                            pass

            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clientes_conectados.discard(websocket)
        print("[CEREBRO] Conexión WebSocket con la Jetson finalizada.")


async def enviar_comando_a_camaras(comando_json):
    """Envía comandos (ej. set_tracking) a todas las cámaras Jetson conectadas."""
    if not clientes_conectados:
        print("[CEREBRO] No hay cámaras Jetson conectadas.")
        return False

    mensaje = json.dumps(comando_json)
    for ws in list(clientes_conectados):
        try:
            await ws.send(mensaje)
            print(f"[CEREBRO] Comando enviado a la Jetson: {comando_json}")
        except Exception as e:
            print(f"[CEREBRO] Error al enviar comando WebSocket: {e}")
    return True


async def iniciar_servidor_ws():
    """Inicia el servidor WebSocket para la Jetson."""
    print(f"[CEREBRO] Escuchando WebSockets en ws://0.0.0.0:{PORT_WS}")
    async with websockets.serve(manejar_cliente, "0.0.0.0", PORT_WS):
        await asyncio.Future()  # Ejecutar indefinidamente


# =====================================================================
# PUNTO DE ENTRADA PRINCIPAL
# =====================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  SARI — Módulo Cerebro v2.0")
    print("  Sistema Autónomo de Respuesta a Intrusiones")
    print("=" * 60)
    print()

    # Registrar handler para limpieza al cerrar
    def _signal_handler(sig, frame):
        print("\n[CEREBRO] Cerrando sistema...")
        _detener_sirena_service()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 1. Arrancar sirena_service.py
    _iniciar_sirena_service()

    # 2. Arrancar el servidor WebSocket
    print()
    try:
        asyncio.run(iniciar_servidor_ws())
    except KeyboardInterrupt:
        _detener_sirena_service()
        print("\n[CEREBRO] Sistema detenido.")
