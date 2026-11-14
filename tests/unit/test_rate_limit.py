"""S12: login and PIN attempts are rate limited (5 failures in 15 min -> 429 for 15 min)."""
import pytest

from app import ratelimit
from app.routers.hardware import HardwareState
from app.telegram import bot

PIN = "4321"
EYE = {"node_id": "Jetson-T", "name": "Test eye"}


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    fake = FakeClock()
    ratelimit.reset_all()
    monkeypatch.setattr(ratelimit, "clock", fake)
    yield fake
    ratelimit.reset_all()


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# --- limiter unit ----------------------------------------------------------------

def test_limiter_locks_after_max_failures_and_releases_after_lockout(clock):
    lim = ratelimit.FailureLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    for _ in range(4):
        lim.record_failure("k")
    assert lim.is_locked("k") is False
    lim.record_failure("k")
    assert lim.is_locked("k") is True
    clock.now += 899
    assert lim.is_locked("k") is True
    clock.now += 2
    assert lim.is_locked("k") is False


def test_limiter_forgets_failures_outside_window(clock):
    lim = ratelimit.FailureLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
    for _ in range(4):
        lim.record_failure("k")
    clock.now += 901
    lim.record_failure("k")
    assert lim.is_locked("k") is False


# --- login -------------------------------------------------------------------------

def test_login_locks_account_after_five_failures(client, make_user):
    make_user("victim", password="right-password")
    for _ in range(5):
        assert _login(client, "victim", "wrong").status_code == 401
    res = _login(client, "victim", "right-password")
    assert res.status_code == 429
    assert "access_token" not in res.text


def test_login_lock_expires_after_fifteen_minutes(client, make_user, clock):
    make_user("victim", password="right-password")
    for _ in range(5):
        _login(client, "victim", "wrong")
    clock.now += 15 * 60 + 1
    assert _login(client, "victim", "right-password").status_code == 200


def test_login_locks_client_ip_across_usernames(client, make_user):
    make_user("other", password="right-password")
    for i in range(5):
        assert _login(client, f"ghost{i}", "wrong").status_code == 401
    assert _login(client, "other", "right-password").status_code == 429


def test_successful_login_resets_account_counter(client, make_user):
    make_user("victim", password="right-password")
    for _ in range(4):
        _login(client, "victim", "wrong")
    assert _login(client, "victim", "right-password").status_code == 200
    ratelimit.login_limiter.reset("ip:testclient")
    for _ in range(4):
        _login(client, "victim", "wrong")
    assert _login(client, "victim", "right-password").status_code == 200


def test_admin_login_still_works(client, make_user):
    make_user("boss", role="admin", password="right-password")
    res = _login(client, "boss", "right-password")
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


# --- PIN -------------------------------------------------------------------------

def test_wrong_pin_locks_user_after_five_failures(client, admin_headers, make_user):
    client.post("/api/eyes", json=EYE, headers=admin_headers)
    op = make_user("op", can_control_hardware=True)
    for _ in range(5):
        res = client.put("/api/eyes/Jetson-T", json={"name": "x", "pin": "0000"}, headers=op)
        assert res.status_code == 401
    res = client.put("/api/eyes/Jetson-T", json={"name": "x", "pin": PIN}, headers=op)
    assert res.status_code == 429
    # another user is not locked out by op's failures
    res = client.put("/api/eyes/Jetson-T", json={"name": "y", "pin": PIN}, headers=admin_headers)
    assert res.status_code == 200


def test_require_pin_keeps_working_without_key():
    from fastapi import HTTPException

    from app.security import require_pin

    require_pin(PIN)
    with pytest.raises(HTTPException) as exc:
        require_pin("0000")
    assert exc.value.status_code == 401


def test_telegram_pin_locks_chat_after_five_failures(siren):
    for _ in range(5):
        assert "PIN" in bot.handle_telegram_command("/sirena 0000", "111")
    reply = bot.handle_telegram_command(f"/sirena {PIN}", "111")
    assert "intentos" in reply.lower()
    assert PIN not in reply
    assert HardwareState.siren_active is False
    assert siren.calls == []


def test_telegram_message_with_many_pins_counts_one_guess(siren):
    guesses = " ".join(f"{i:04d}" for i in range(0, 40))
    bot.handle_telegram_command(f"activa la sirena {guesses} {PIN}", "111")
    assert HardwareState.siren_active is True  # last token is the PIN
    HardwareState.siren_active = False
    bot.handle_telegram_command(f"activa la sirena {PIN} {guesses}", "111")
    assert HardwareState.siren_active is False  # only the last numeric token is tried


def test_manual_action_wrong_pins_lock_the_user(client, admin_headers, siren):
    for _ in range(5):
        res = client.post("/api/hardware/manual_action", json={"action": "activar_sirena", "pin": "0000"}, headers=admin_headers)
        assert res.status_code == 401
    res = client.post("/api/hardware/manual_action", json={"action": "activar_sirena", "pin": "4321"}, headers=admin_headers)
    assert res.status_code == 429
    assert siren.calls == []


def test_chat_thread_creation_wrong_pins_lock_the_user(client, admin_headers):
    for _ in range(5):
        assert client.post("/api/chat", json={"message": "hola", "pin": "0000"}, headers=admin_headers).status_code == 401
    assert client.post("/api/chat", json={"message": "hola", "pin": "4321"}, headers=admin_headers).status_code == 429
