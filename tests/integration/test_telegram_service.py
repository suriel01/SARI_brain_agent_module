import os
import json
import pytest
from unittest.mock import patch, MagicMock

def test_telegram_security_and_whitelist():
    os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = "987654321,11223344"

    from app.telegram.service import is_chat_allowed, get_default_chat_id

    assert is_chat_allowed(987654321) is True
    assert is_chat_allowed("987654321") is True
    assert is_chat_allowed(11223344) is True
    assert is_chat_allowed(99999999) is False
    assert is_chat_allowed("unknown_intruder") is False

    assert get_default_chat_id() == "987654321"

def test_telegram_send_message_mocked():
    from app.telegram.service import send_telegram_message

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": True}

        success = send_telegram_message("🛡️ Test Message from SARI SOC", chat_id="987654321")
        assert success is True
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert "sendMessage" in args[0]
        assert kwargs["json"]["chat_id"] == "987654321"
        assert "Test Message" in kwargs["json"]["text"]

def test_telegram_send_alert_photo_mocked():
    from app.telegram.service import send_telegram_alert_photo

    # 1x1 transparent png in base64
    test_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": True}

        success = send_telegram_alert_photo(
            photo_base64_or_bytes=test_b64,
            caption="🚨 ALERTA DE PRUEBA JETSON",
            chat_id="987654321"
        )
        assert success is True
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert "sendPhoto" in args[0]
        assert kwargs["data"]["chat_id"] == "987654321"
        assert "ALERTA DE PRUEBA" in kwargs["data"]["caption"]
        assert "photo" in kwargs["files"]

def test_telegram_command_dispatcher():
    from app.telegram.bot import handle_telegram_command
    from app.routers.hardware import HardwareState

    # 1. Unauthorized chat
    unauth_resp = handle_telegram_command("/status", from_chat_id="666666")
    assert "no autorizado" in unauth_resp.lower() or "unauthorized" in unauth_resp.lower()

    # 2. Status command
    status_resp = handle_telegram_command("/status", from_chat_id="987654321")
    assert "SARI" in status_resp
    assert "Sirena" in status_resp

    # 3. Siren with wrong PIN
    bad_pin_resp = handle_telegram_command("/sirena 0000", from_chat_id="987654321")
    assert "PIN inválido" in bad_pin_resp or "PIN incorrecto" in bad_pin_resp

    # 4. Siren with correct PIN (1234)
    siren_resp = handle_telegram_command("/sirena 1234", from_chat_id="987654321")
    assert "activada" in siren_resp.lower()
    assert HardwareState.siren_active is True

    # 5. Silence command
    silence_resp = handle_telegram_command("/silenciar", from_chat_id="987654321")
    assert "silenciada" in silence_resp.lower() or "apagada" in silence_resp.lower()
    assert HardwareState.siren_active is False
    print("[+] test_telegram_service tests passed successfully!")


def test_mqtt_handlers_telegram_integration():
    from unittest.mock import patch
    from app.mqtt.handlers import handle_alert_message, handle_status_message
    from app.telegram.watchdog import _disconnected_nodes_notified

    _disconnected_nodes_notified.clear()

    # Test 1: handle_alert_message dispatches to send_telegram_alert_photo
    with patch("app.mqtt.handlers.send_telegram_alert_photo") as mock_tg_photo:
        payload = json.dumps({
            "camara_id": "Jetson-INTEGRATION-TEST",
            "message": "Intrusión verificada en caseta",
            "severity": "high",
            "confidence": 0.95,
            "snapshot": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        })
        handle_alert_message(payload)
        assert mock_tg_photo.called
        args, kwargs = mock_tg_photo.call_args
        assert "Jetson-INTEGRATION-TEST" in kwargs.get("caption", "")
        assert kwargs.get("reply_markup") is not None

    # Test 2: handle_status_message with LWT offline triggers watchdog alert (text only with action buttons)
    with patch("app.telegram.service.send_telegram_message") as mock_watchdog_msg:
        handle_status_message("sari/nodes/Jetson-LWT-TEST/status", json.dumps({"status": "offline"}))
        assert mock_watchdog_msg.called
        args, kwargs = mock_watchdog_msg.call_args
        msg_text = args[0] if args else kwargs.get("text", "")
        assert "Jetson-LWT-TEST" in msg_text
        assert "SABOTAJE" in msg_text
        assert kwargs.get("reply_markup") is not None


def test_telegram_photo_commands():
    from unittest.mock import patch
    from app.telegram.bot import handle_telegram_command

    # 1. Request specific module with mock
    with patch("app.telegram.bot.send_telegram_alert_photo") as mock_photo:
        res = handle_telegram_command("/foto Jetson-PTZ_1", from_chat_id="987654321")
        # Should have attempted to fetch or send, or returned status
        assert "no encontrado" not in res.lower()

    # 2. Request all modules
    with patch("app.telegram.bot.send_telegram_alert_photo") as mock_photo,          patch("app.telegram.bot.send_telegram_message") as mock_msg:
        res = handle_telegram_command("/fotos", from_chat_id="987654321")
        assert mock_photo.called or "transmisión" in res.lower() or res == ""

    # 3. Request unknown module
    res_unknown = handle_telegram_command("/foto ModuloInexistente99", from_chat_id="987654321")
    assert "no configurado" in res_unknown.lower() or "no encontrado" in res_unknown.lower()

if __name__ == "__main__":
    test_telegram_security_and_whitelist()
    test_telegram_send_message_mocked()
    test_telegram_send_alert_photo_mocked()
    test_telegram_command_dispatcher()
