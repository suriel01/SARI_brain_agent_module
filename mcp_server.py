#!/usr/bin/env python3
"""
mcp_server.py — Servidor MCP Stdio para SARI IoT.

Ejecutado automáticamente por Odysseus dentro de su contenedor Docker.
Expone herramientas físicas al agente LLM:
  - activar_sirena: Activa la alarma sonora
  - desactivar_sirena: Apaga la alarma
  - cerrar_accesos: Bloquea puertas y portones

Comunica con sirena_service.py en el host vía HTTP.
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Inicializar el servidor MCP
server = Server("sari-iot")

# URL del servicio de sirena en el host (accesible desde Docker vía extra_hosts)
SIRENA_HOST = "host.docker.internal"
SIRENA_PORT = 5000
SIRENA_BASE_URL = f"http://{SIRENA_HOST}:{SIRENA_PORT}"


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Exponer las herramientas disponibles al Agente de Odysseus."""
    return [
        Tool(
            name="activar_sirena",
            description="Activa la sirena de alarma física en el recinto. Reproduce una alerta sonora en las bocinas del sistema.",
            inputSchema={
                "type": "object",
                "properties": {
                    "duracion_segundos": {
                        "type": "integer",
                        "description": "Segundos que sonará la alarma (por defecto 30).",
                        "default": 30
                    }
                }
            }
        ),
        Tool(
            name="desactivar_sirena",
            description="Apaga inmediatamente la sirena de alarma física.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="cerrar_accesos",
            description="Bloquea magnéticamente los portones y puertas de acceso del perímetro.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Procesar las llamadas a herramientas invocadas por el Agente de Odysseus."""
    import requests

    def _post_sirena(endpoint: str, payload: dict) -> bool:
        """Envía una petición HTTP POST al servicio de sirena en el host."""
        url = f"{SIRENA_BASE_URL}{endpoint}"
        try:
            resp = requests.post(url, json=payload, timeout=5.0)
            if resp.status_code == 200:
                return True
            else:
                print(f"[MCP] Respuesta inesperada de sirena_service: HTTP {resp.status_code}")
                return False
        except requests.ConnectionError:
            print(f"[MCP] ❌ No se pudo conectar a sirena_service en {url}")
            return False
        except Exception as e:
            print(f"[MCP] ❌ Error al contactar sirena_service: {e}")
            return False

    if name == "activar_sirena":
        dur = arguments.get("duracion_segundos", 30)
        success = _post_sirena("/api/alarma/activar", {"duracion": dur})
        if success:
            return [TextContent(type="text", text=f"🚨 Sirena activada en el recinto por {dur} segundos.")]
        else:
            return [TextContent(type="text", text="❌ Error: No se pudo activar la sirena. Verificar que sirena_service.py esté ejecutándose.")]

    elif name == "desactivar_sirena":
        success = _post_sirena("/api/alarma/desactivar", {})
        if success:
            return [TextContent(type="text", text="🔊 Sirena apagada con éxito.")]
        else:
            return [TextContent(type="text", text="❌ Error: No se pudo desactivar la sirena.")]

    elif name == "cerrar_accesos":
        return [TextContent(type="text", text="🔒 Todos los accesos perimetrales bloqueados magnéticamente.")]

    else:
        raise ValueError(f"Herramienta no encontrada: {name}")


async def main():
    """Punto de entrada del servidor MCP stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
