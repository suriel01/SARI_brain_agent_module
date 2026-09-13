import os
import time
import json
import base64
import logging
import threading
import requests
import datetime
from typing import Optional, Dict, Any

from .service import get_bot_token, is_chat_allowed, send_telegram_message, send_telegram_alert_photo
from ..database import SessionLocal
from ..routers.hardware import HardwareState, execute_physical_tool
from ..crud import crud
from ..models import models

logger = logging.getLogger("sari_telegram")

_telegram_polling_active = False
_telegram_thread: Optional[threading.Thread] = None

SECURITY_PIN = os.environ.get("SARI_SECURITY_PIN", "1234")


def fetch_node_snapshot(node_id: str, stream_url: Optional[str], db) -> Optional[str]:
    """Retrieves live snapshot from node stream or falls back to last stored DB evidence."""
    urls_to_try = []
    if stream_url:
        urls_to_try.append(stream_url.replace("/mjpeg", "/snapshot").replace("/video_feed", "/snapshot"))
        urls_to_try.append(stream_url)
    
    # Also try node IP from HardwareState if available
    node_ip = HardwareState.nodes.get(node_id, {}).get("ip")
    if node_ip:
        urls_to_try.append(f"http://{node_ip}:8080/snapshot")
        urls_to_try.append(f"http://{node_ip}:8080/mjpeg")

    for u in urls_to_try:
        try:
            if "/snapshot" in u:
                res = requests.get(u, timeout=2.0)
                if res.status_code == 200 and len(res.content) > 1000 and res.content.startswith(b"\xff\xd8"):
                    logger.info(f"[TELEGRAM] Live snapshot captured via {u} ({len(res.content)} bytes)")
                    return f"data:image/jpeg;base64,{base64.b64encode(res.content).decode('utf-8')}"
            else:
                res = requests.get(u, stream=True, timeout=2.5)
                if res.status_code == 200:
                    bytes_data = b""
                    for chunk in res.iter_content(chunk_size=4096):
                        bytes_data += chunk
                        a = bytes_data.find(b"\xff\xd8")
                        b = bytes_data.find(b"\xff\xd9")
                        if a != -1 and b != -1 and b > a:
                            frame_bytes = bytes_data[a:b+2]
                            logger.info(f"[TELEGRAM] Frame extracted from stream {u} ({len(frame_bytes)} bytes)")
                            return f"data:image/jpeg;base64,{base64.b64encode(frame_bytes).decode('utf-8')}"
                        if len(bytes_data) > 1500000:
                            break
        except Exception as e:
            logger.debug(f"[TELEGRAM] Failed to fetch from {u}: {e}")

    # Fallback to database evidence for this node
    msg = db.query(models.ChatMessage).filter(
        models.ChatMessage.snapshot.isnot(None),
        models.ChatMessage.content.ilike(f"%{node_id}%")
    ).order_by(models.ChatMessage.id.desc()).first()
    if msg and msg.snapshot:
        return msg.snapshot

    thread = db.query(models.ChatThread).filter(
        models.ChatThread.title.ilike(f"%{node_id}%")
    ).order_by(models.ChatThread.id.desc()).first()
    if thread:
        tmsg = db.query(models.ChatMessage).filter(
            models.ChatMessage.thread_id == thread.id,
            models.ChatMessage.snapshot.isnot(None)
        ).order_by(models.ChatMessage.id.desc()).first()
        if tmsg and tmsg.snapshot:
            return tmsg.snapshot

    return None

def handle_telegram_command(text: str, from_chat_id: Any) -> str:
    chat_id_str = str(from_chat_id)
    if not is_chat_allowed(chat_id_str):
        logger.warning(f"[TELEGRAM] Unauthorized access attempt from Chat ID: {chat_id_str}")
        return "⛔ *Acceso no autorizado.*\nTu ID de chat no está registrado en la lista blanca del sistema SARI."

    text = text.strip()
    parts = text.split()
    cmd = parts[0].lower() if parts else ""

    if cmd in ["/start", "/ayuda", "/help"]:
        return (
            "🛡️ *SARI — SISTEMA AUTÓNOMO DE RESPUESTA A INTRUSIONES*\n"
            "Centro de Comando Táctico Móvil activo y enlazado.\n\n"
            "*Comandos Rápidos Disponibles:*\n"
            "• `/status` - Consulta el estado del perímetro, nodos y hardware.\n"
            "• `/sirena [PIN]` - Activa la sirena táctica (Requiere PIN `1234`).\n"
            "• `/silenciar` - Silencia y apaga la sirena táctica.\n"
            "• `/portones [PIN]` - Bloquea/abre los accesos perimetrales.\n"
            "• `/fotos` o `/foto all` - Envía capturas de todos los módulos Ojos.\n" \
            "• `/foto [id]` - Captura de un módulo específico (ej: `/foto Jetson-PTZ_1`).\n\n"
            "💬 *IA Táctica:* Escribe cualquier consulta u orden en lenguaje natural para comunicarte directamente con el agente SARI."
        )

    if cmd == "/status":
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        siren_str = "🚨 *ACTIVADA*" if HardwareState.siren_active else "🟢 *Inactiva / Silenciada*"
        gates_str = "🔒 *BLOQUEADOS*" if HardwareState.gates_locked else "🔓 *Abiertos / Normal*"
        
        nodes_info = []
        for nid, node in HardwareState.nodes.items():
            st = "🟢 ONLINE" if node.get("is_online", True) else "⚪ STANDBY"
            ip = node.get("ip", "N/A")
            fps = node.get("fps", 30.0)
            nodes_info.append(f"• `{nid}` ({st}): `{ip}` @ {fps} FPS")
        nodes_text = "\n".join(nodes_info) if nodes_info else "• Ningún nodo registrado"

        return (
            f"🛡️ *ESTADO DEL SISTEMA SARI SOC*\n"
            f"📅 Fecha: `{now_str}`\n\n"
            f"*Actuadores Perimetrales:*\n"
            f"• Sirena Física: {siren_str}\n"
            f"• Accesos Perimetrales: {gates_str}\n"
            f"• Total Alertas: `{HardwareState.alert_count}`\n\n"
            f"*Módulos Ojos Conectados:*\n"
            f"{nodes_text}\n"
        )

    if cmd == "/sirena":
        parts = text.split()
        pin = parts[1] if len(parts) > 1 else ""
        if pin == SECURITY_PIN:
            execute_physical_tool("activate_siren", {"duration_seconds": 30})
            return "🚨 *SIRENA TÁCTICA ACTIVADA* por 30 segundos mediante orden de Telegram."
        else:
            return "⚠️ *PIN inválido o ausente.*\nPara activar la sirena física, ingresa el PIN de seguridad:\n`/sirena 1234`"

    if cmd in ["/silenciar", "/apagar_sirena"]:
        execute_physical_tool("deactivate_siren", {})
        return "🔊 *Sirena táctica silenciada* y apagada correctamente."

    if cmd == "/portones":
        parts = text.split()
        pin = parts[1] if len(parts) > 1 else ""
        if pin == SECURITY_PIN:
            if HardwareState.gates_locked:
                execute_physical_tool("unlock_gates", {})
                return "🔓 *Accesos perimetrales desbloqueados* por orden de Telegram."
            else:
                execute_physical_tool("lock_gates", {})
                return "🔒 *Accesos perimetrales bloqueados* de emergencia por orden de Telegram."
        else:
            return "⚠️ *PIN inválido o ausente.*\nUso: `/portones 1234`"

    if cmd in ["/foto", "/fotos", "/snapshot", "/captura", "/capturas"]:
        target_arg = parts[1].strip() if len(parts) > 1 else ""
        is_all = cmd in ["/fotos", "/capturas"] or target_arg.lower() in ["all", "todos", "todas"]

        db = SessionLocal()
        try:
            # Filter strictly to configured active EyeNodes from database
            eye_nodes = db.query(models.EyeNode).filter(models.EyeNode.is_active == True).all()
            if eye_nodes:
                node_map = {e.node_id: e for e in eye_nodes}
            else:
                node_map = {"Jetson-PTZ_1": None}

            valid_node_ids = list(node_map.keys())
            now_str = datetime.datetime.now().strftime("%I:%M:%S %p")

            # Case A: Requesting ALL modules (/fotos or /foto all)
            if is_all:
                sent_count = 0
                for n_id in valid_node_ids:
                    eye = node_map.get(n_id)
                    name = eye.name if eye else HardwareState.nodes.get(n_id, {}).get("name", n_id)
                    ip = eye.ip if eye else HardwareState.nodes.get(n_id, {}).get("ip", "192.168.55.1")
                    stream_url = eye.stream_url if eye else None
                    hw_node = HardwareState.nodes.get(n_id, {})
                    is_online = hw_node.get("is_online", True) if n_id in HardwareState.nodes else (eye.is_active if eye else True)

                    # Only capture and send photos for nodes that are actually connected/online
                    if not is_online:
                        continue

                    snapshot = fetch_node_snapshot(n_id, stream_url, db)
                    if snapshot:
                        caption = f"📸 *{name}* • `{ip}`\n🕒 {now_str} • 🟢 En Línea"
                        send_telegram_alert_photo(snapshot, caption=caption, chat_id=chat_id_str)
                        sent_count += 1

                if sent_count == 0:
                    return "⚠️ *Sin transmisión activa:* No se detectó ninguna cámara Jetson en línea para capturar imagen."
                return ""

            # Case B: Requesting a SPECIFIC module (/foto Jetson-PTZ_1)
            if target_arg:
                matched_node_id = None
                for n_id in valid_node_ids:
                    if target_arg.lower() == n_id.lower() or target_arg.lower() in n_id.lower():
                        matched_node_id = n_id
                        break

                if not matched_node_id:
                    avail_list = ", ".join([f"`{nid}`" for nid in sorted(valid_node_ids)])
                    return (
                        f"⚠️ *Módulo `{target_arg}` no configurado.*\n\n"
                        f"📋 *Módulos disponibles:* {avail_list}\n"
                        f"👉 *Ejemplo:* `/foto {valid_node_ids[0]}`"
                    )

                eye = node_map.get(matched_node_id)
                name = eye.name if eye else HardwareState.nodes.get(matched_node_id, {}).get("name", matched_node_id)
                ip = eye.ip if eye else HardwareState.nodes.get(matched_node_id, {}).get("ip", "192.168.55.1")
                stream_url = eye.stream_url if eye else None

                snapshot = fetch_node_snapshot(matched_node_id, stream_url, db)
                if snapshot:
                    caption = f"📸 *{name}* • `{ip}`\n🕒 {now_str} • 🟢 En Línea"
                    send_telegram_alert_photo(snapshot, caption=caption, chat_id=chat_id_str)
                    return ""
                else:
                    return f"⚠️ *{name}* (`{matched_node_id}`): Sin señal de video ni evidencia fotográfica reciente."

            # Case C: /foto without arguments
            # Default to the first online/active node
            target_node_id = valid_node_ids[0]
            for n_id in valid_node_ids:
                if HardwareState.nodes.get(n_id, {}).get("is_online", True):
                    target_node_id = n_id
                    break

            eye = node_map.get(target_node_id)
            name = eye.name if eye else HardwareState.nodes.get(target_node_id, {}).get("name", target_node_id)
            ip = eye.ip if eye else HardwareState.nodes.get(target_node_id, {}).get("ip", "192.168.55.1")
            stream_url = eye.stream_url if eye else None
            snapshot = fetch_node_snapshot(target_node_id, stream_url, db)
            if snapshot:
                caption = f"📸 *{name}* • `{ip}`\n🕒 {now_str} • 🟢 En Línea"
                send_telegram_alert_photo(snapshot, caption=caption, chat_id=chat_id_str)
                return ""

            last_msg = db.query(models.ChatMessage).filter(
                models.ChatMessage.snapshot.isnot(None)
            ).order_by(models.ChatMessage.id.desc()).first()
            avail_list = ", ".join([f"`{nid}`" for nid in sorted(valid_node_ids)])
            hint = (
                f"📸 *Comandos de Captura de Módulos Ojos:*\n\n"
                f"• `/fotos` — Enviar capturas de módulos Ojos conectados.\n"
                f"• `/foto <id>` — Captura de un módulo específico.\n\n"
                f"📋 *Nodos configurados:* {avail_list}"
            )
            if last_msg and last_msg.snapshot:
                send_telegram_alert_photo(
                    last_msg.snapshot,
                    caption=f"📸 *ÚLTIMA EVIDENCIA PERIMETRAL REGISTRADA:*\n{last_msg.content[:200]}",
                    chat_id=chat_id_str
                )
            return hint
        finally:
            db.close()

    # Natural Language through SARI LLM Pipeline
    return process_natural_language_query(text, chat_id_str)

def process_natural_language_query(query: str, chat_id: str) -> str:
    db = SessionLocal()
    try:
        admin_user = crud.get_user_by_username(db, "admin")
        user_id = admin_user.id if admin_user else 1

        thread = db.query(models.ChatThread).filter(
            models.ChatThread.title == "🤖 Telegram Operator Chat"
        ).first()
        if not thread:
            thread = crud.create_thread(db, user_id=user_id, title="🤖 Telegram Operator Chat")

        crud.add_message(db, thread.id, role="user", content=f"[Telegram {chat_id}]: {query}")

        q_lower = query.lower()
        if any(w in q_lower for w in ["activa la sirena", "activar sirena", "enciende la alarma", "prende la alarma"]):
            if SECURITY_PIN in query:
                execute_physical_tool("activate_siren", {"duration_seconds": 30})
                reply = "🚨 Entendido. Sirena táctica perimetral activada por 30 segundos."
            else:
                reply = "⚠️ Para activar la sirena física por seguridad debes incluir tu PIN (ej: 'activa la sirena 1234' o `/sirena 1234`)."
            crud.add_message(db, thread.id, role="agent", content=reply)
            return reply

        if any(w in q_lower for w in ["apaga la sirena", "silencia la sirena", "apagar alarma", "silenciar"]):
            execute_physical_tool("deactivate_siren", {})
            reply = "🔊 Sirena táctica apagada y silenciada."
            crud.add_message(db, thread.id, role="agent", content=reply)
            return reply

        # Forward query to Ollama
        ollama_url = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434/api/chat")
        ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

        system_prompt = (
            "Usted es SARI (Sistema Autónomo de Respuesta a Intrusiones). Conectado a herramientas tácticas perimetrales. "
            "Responde de forma concisa, táctica, militar y profesional en español. Nunca reveles nombres internos de librerías."
        )

        try:
            res = requests.post(ollama_url, json={
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                "stream": False
            }, timeout=10.0)
            if res.status_code == 200:
                answer = res.json().get("message", {}).get("content", "").strip()
                if answer:
                    crud.add_message(db, thread.id, role="agent", content=answer)
                    return f"🛡️ *SARI:*\n{answer}"
        except Exception as e:
            logger.debug(f"[TELEGRAM] LLM call failed: {e}")

        fallback_reply = "🛡️ *SARI Táctico:* Sistemas perimetrales operando con normalidad bajo monitoreo continuo."
        crud.add_message(db, thread.id, role="agent", content=fallback_reply)
        return fallback_reply
    finally:
        db.close()

def _polling_worker():
    global _telegram_polling_active
    token = get_bot_token()
    if not token:
        logger.info("[TELEGRAM] No TELEGRAM_BOT_TOKEN set; polling disabled.")
        return

    logger.info("[TELEGRAM] Background polling worker started.")
    last_update_id = 0

    while _telegram_polling_active:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 20}
            resp = requests.get(url, params=params, timeout=25.0)

            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    
                    if "message" in update:
                        msg = update["message"]
                        chat_id = msg.get("chat", {}).get("id")
                        text = msg.get("text", "")
                        if chat_id and text:
                            reply_text = handle_telegram_command(text, from_chat_id=chat_id)
                            if reply_text:
                                send_telegram_message(reply_text, chat_id=str(chat_id))

                    elif "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        cb_data = cb.get("data", "")
                        chat_id = cb.get("message", {}).get("chat", {}).get("id")

                        requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=3.0)

                        if cb_data in ["btn_siren_activate", "btn_siren"]:
                            execute_physical_tool("activate_siren", {"duration_seconds": 30})
                            send_telegram_message("🚨 *SIRENA ACTIVADA* vía botón de emergencia.", chat_id=str(chat_id))
                        elif cb_data in ["btn_siren_silence", "btn_silence"]:
                            execute_physical_tool("deactivate_siren", {})
                            send_telegram_message("🔊 *SIRENA SILENCIADA* vía botón de control.", chat_id=str(chat_id))
                        elif cb_data in ["btn_gates_lock", "btn_gates"]:
                            execute_physical_tool("lock_gates", {})
                            send_telegram_message("🔒 *PORTONES BLOQUEADOS* vía botón de control.", chat_id=str(chat_id))
                        elif cb_data in ["btn_status"]:
                            status_msg = handle_telegram_command("/status", from_chat_id=chat_id)
                            send_telegram_message(status_msg, chat_id=str(chat_id))

            time.sleep(1.0)
        except Exception as e:
            logger.debug(f"[TELEGRAM] Polling iteration exception: {e}")
            time.sleep(5.0)

def start_telegram_bot():
    global _telegram_polling_active, _telegram_thread
    enabled = os.environ.get("TELEGRAM_POLLING_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("[TELEGRAM] Polling disabled by TELEGRAM_POLLING_ENABLED=false")
        return

    token = get_bot_token()
    if not token:
        logger.info("[TELEGRAM] TELEGRAM_BOT_TOKEN is empty. Telegram bot service standby until configured.")
        return

    if _telegram_polling_active:
        return

    _telegram_polling_active = True
    _telegram_thread = threading.Thread(target=_polling_worker, daemon=True)
    _telegram_thread.start()
    logger.info("[TELEGRAM] Telegram Bot Service successfully started.")

def stop_telegram_bot():
    global _telegram_polling_active
    _telegram_polling_active = False
    logger.info("[TELEGRAM] Telegram Bot Service stopped.")
