import os
import io
import json
import base64
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger("sari_telegram")

def get_bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

def get_allowed_chat_ids() -> list:
    raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    if not raw:
        return []
    return [cid.strip() for cid in raw.replace(";", ",").split(",") if cid.strip()]

def is_chat_allowed(chat_id: Any) -> bool:
    allowed = get_allowed_chat_ids()
    if not allowed:
        # If no chat IDs are explicitly restricted, allow none unless configured
        return False
    return str(chat_id).strip() in allowed

def get_default_chat_id() -> Optional[str]:
    allowed = get_allowed_chat_ids()
    return allowed[0] if allowed else None

def send_telegram_message(text: str, chat_id: Optional[str] = None, reply_markup: Optional[dict] = None) -> bool:
    token = get_bot_token()
    target_chat = chat_id or get_default_chat_id()

    if not token or not target_chat:
        logger.debug("[TELEGRAM] Missing bot token or target chat id; message not dispatched.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": str(target_chat),
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        res = requests.post(url, json=payload, timeout=4.0)
        if res.status_code == 200:
            return True
        if res.status_code == 400 and ("parse" in res.text.lower() or "entities" in res.text.lower()):
            payload.pop("parse_mode", None)
            res2 = requests.post(url, json=payload, timeout=4.0)
            if res2.status_code == 200:
                return True
        logger.warning(f"[TELEGRAM] Send message failed ({res.status_code}): {res.text}")
        return False
    except Exception as e:
        logger.warning(f"[TELEGRAM] Network error sending message: {e}")
        return False

def send_telegram_alert_photo(
    photo_base64_or_bytes: Any,
    caption: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[dict] = None
) -> bool:
    token = get_bot_token()
    target_chat = chat_id or get_default_chat_id()

    if not token or not target_chat:
        logger.debug("[TELEGRAM] Missing bot token or target chat id; photo alert not dispatched.")
        return False

    try:
        if isinstance(photo_base64_or_bytes, str):
            clean_b64 = photo_base64_or_bytes
            if "base64," in clean_b64:
                clean_b64 = clean_b64.split("base64,")[1]
            raw_bytes = base64.b64decode(clean_b64)
        elif isinstance(photo_base64_or_bytes, bytes):
            raw_bytes = photo_base64_or_bytes
        else:
            return send_telegram_message(caption, chat_id=target_chat, reply_markup=reply_markup)

        bio = io.BytesIO(raw_bytes)
        bio.name = "evidence.jpg"

        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        data: Dict[str, Any] = {
            "chat_id": str(target_chat),
            "caption": caption[:1024],
            "parse_mode": "Markdown"
        }
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

        files = {"photo": ("evidence.jpg", bio, "image/jpeg")}
        res = requests.post(url, data=data, files=files, timeout=7.0)

        if res.status_code == 200:
            logger.info("[TELEGRAM] Alert photo successfully delivered.")
            return True

        # If markdown formatting failed, retry sending photo with plain text caption
        if res.status_code == 400 and ("parse" in res.text.lower() or "entities" in res.text.lower()):
            bio.seek(0)
            data.pop("parse_mode", None)
            res2 = requests.post(url, data=data, files={"photo": ("evidence.jpg", bio, "image/jpeg")}, timeout=7.0)
            if res2.status_code == 200:
                logger.info("[TELEGRAM] Alert photo delivered without Markdown parsing.")
                return True

        logger.warning(f"[TELEGRAM] Send photo failed ({res.status_code}): {res.text}. Falling back to text.")
        return send_telegram_message(caption, chat_id=target_chat, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"[TELEGRAM] Error sending alert photo: {e}. Falling back to text.")
        return send_telegram_message(caption, chat_id=target_chat, reply_markup=reply_markup)
