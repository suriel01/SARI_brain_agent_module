"""S9: Telegram callbacks enforce the chat allowlist; silencing requires the security PIN."""
import pytest

from app.routers.hardware import HardwareState
from app.telegram import bot

ALLOWED = "111"
STRANGER = "999"
PIN = "4321"


@pytest.fixture
def siren_on(siren):
    HardwareState.siren_active = True
    return siren


# --- callbacks -------------------------------------------------------------

@pytest.mark.parametrize("cb", ["btn_siren_activate", "btn_siren", "btn_silence", "btn_siren_silence",
                                "btn_gates_lock", "btn_gates", "btn_status"])
def test_callback_from_unlisted_chat_does_nothing(siren_on, cb):
    reply = bot.handle_telegram_callback(cb, STRANGER)
    assert reply is None
    assert siren_on.calls == []
    assert HardwareState.siren_active is True
    assert HardwareState.gates_locked is False


def test_callback_without_chat_does_nothing(siren):
    assert bot.handle_telegram_callback("btn_siren_activate", None) is None
    assert siren.calls == []
    assert HardwareState.siren_active is False


@pytest.mark.parametrize("cb", ["btn_silence", "btn_siren_silence"])
def test_silence_button_asks_for_pin_instead_of_silencing(siren_on, cb):
    reply = bot.handle_telegram_callback(cb, ALLOWED)
    assert "/silenciar <PIN>" in reply
    assert PIN not in reply
    assert siren_on.calls == []
    assert HardwareState.siren_active is True


@pytest.mark.parametrize("cb", ["btn_gates_lock", "btn_gates"])
def test_gates_button_asks_for_pin_instead_of_locking(siren, cb):
    reply = bot.handle_telegram_callback(cb, ALLOWED)
    assert "/portones <PIN>" in reply
    assert PIN not in reply
    assert siren.calls == []
    assert HardwareState.gates_locked is False


def test_activate_button_still_one_tap_for_allowed_chat(siren):
    reply = bot.handle_telegram_callback("btn_siren_activate", ALLOWED)
    assert "SIRENA ACTIVADA" in reply
    assert HardwareState.siren_active is True
    assert len(siren.calls) == 1


def test_status_button_still_reports_for_allowed_chat(siren):
    reply = bot.handle_telegram_callback("btn_status", ALLOWED)
    assert "ESTADO DEL SISTEMA" in reply


def test_unknown_callback_returns_nothing(siren):
    assert bot.handle_telegram_callback("btn_whatever", ALLOWED) is None
    assert siren.calls == []


# --- silence commands --------------------------------------------------------

@pytest.mark.parametrize("cmd", ["/silenciar", "/apagar_sirena", "/silenciar 0000"])
def test_silence_command_without_valid_pin_is_rejected(siren_on, cmd):
    reply = bot.handle_telegram_command(cmd, ALLOWED)
    assert "PIN" in reply
    assert PIN not in reply
    assert siren_on.calls == []
    assert HardwareState.siren_active is True


@pytest.mark.parametrize("cmd", ["/silenciar", "/apagar_sirena"])
def test_silence_command_with_pin_silences(siren_on, cmd):
    reply = bot.handle_telegram_command(f"{cmd} {PIN}", ALLOWED)
    assert "silenciada" in reply.lower()
    assert HardwareState.siren_active is False
    assert PIN not in reply


def test_silence_command_from_unlisted_chat_is_rejected(siren_on):
    reply = bot.handle_telegram_command(f"/silenciar {PIN}", STRANGER)
    assert "no autorizado" in reply
    assert HardwareState.siren_active is True


@pytest.mark.parametrize("text", ["apaga la sirena", "silenciar ahora", "silencia la sirena 0000"])
def test_natural_language_silence_without_pin_is_rejected(siren_on, text):
    reply = bot.handle_telegram_command(text, ALLOWED)
    assert "PIN" in reply
    assert PIN not in reply
    assert siren_on.calls == []
    assert HardwareState.siren_active is True


def test_natural_language_silence_with_pin_silences(siren_on):
    reply = bot.handle_telegram_command(f"apaga la sirena {PIN}", ALLOWED)
    assert HardwareState.siren_active is False
    assert PIN not in reply


# --- previous behavior still holds -------------------------------------------

def test_sirena_command_with_pin_still_activates(siren):
    reply = bot.handle_telegram_command(f"/sirena {PIN}", ALLOWED)
    assert "ACTIVADA" in reply
    assert HardwareState.siren_active is True


def test_help_mentions_pin_for_silence(siren):
    reply = bot.handle_telegram_command("/help", ALLOWED)
    assert "/silenciar [PIN]" in reply


def test_natural_language_pin_is_not_stored_in_chat_history(siren):
    from app.database import SessionLocal
    from app.models import models

    bot.handle_telegram_command(f"activa la sirena {PIN}", ALLOWED)
    db = SessionLocal()
    try:
        contents = [m.content for m in db.query(models.ChatMessage).all()]
    finally:
        db.close()
    assert contents and not any(PIN in c for c in contents)
