"""S4/T6: physical state reflects reality; explicit actions set state, failures are reported, gates are simulated."""
import logging

import pytest

from app.routers import hardware
from app.routers.hardware import Actor, HardwareState, execute_physical_tool
from conftest import SirenRecorder

ADMIN = Actor("admin_u", "rest", True)


def _manual(client, headers, action):
    return client.post("/api/hardware/manual_action", json={"action": action, "pin": "4321"}, headers=headers)


def _audit_results():
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        return [(r.action, r.result) for r in db.query(models.PhysicalActionLog).order_by(models.PhysicalActionLog.id).all()]
    finally:
        db.close()


class _HttpError:
    """Siren service answering with a non-2xx status."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, *args, **kwargs):
        self.calls.append(url)

        class _Resp:
            status_code = 503

        return _Resp()


@pytest.mark.parametrize("action", ["activar_sirena", "activate_siren"])
def test_repeated_activate_keeps_siren_on(client, admin_headers, siren, action):
    assert _manual(client, admin_headers, action).json()["status"] == "success"
    assert _manual(client, admin_headers, action).json()["status"] == "success"
    assert HardwareState.siren_active is True
    assert all(c["url"].endswith("/api/alarma/activar") for c in siren.calls)


@pytest.mark.parametrize("action", ["desactivar_sirena", "deactivate_siren"])
def test_deactivate_when_off_stays_off(client, admin_headers, siren, action):
    assert _manual(client, admin_headers, action).json()["status"] == "success"
    assert HardwareState.siren_active is False
    assert siren.calls[0]["url"].endswith("/api/alarma/desactivar")


@pytest.mark.parametrize("lock,unlock", [("cerrar_accesos", "abrir_accesos"), ("lock_gates", "unlock_gates")])
def test_gate_actions_set_state(client, admin_headers, siren, lock, unlock):
    _manual(client, admin_headers, lock)
    _manual(client, admin_headers, lock)
    assert HardwareState.gates_locked is True
    _manual(client, admin_headers, unlock)
    _manual(client, admin_headers, unlock)
    assert HardwareState.gates_locked is False


def test_legacy_toggle_actions_still_toggle(client, admin_headers, siren):
    """Previous behaviour the UI relies on (HardwarePanel/Dashboard send toggle_*)."""
    _manual(client, admin_headers, "toggle_sirena")
    assert HardwareState.siren_active is True
    _manual(client, admin_headers, "toggle_sirena")
    assert HardwareState.siren_active is False
    _manual(client, admin_headers, "toggle_accesos")
    assert HardwareState.gates_locked is True
    _manual(client, admin_headers, "toggle_accesos")
    assert HardwareState.gates_locked is False


def test_unknown_manual_action_is_400(client, admin_headers, siren):
    assert _manual(client, admin_headers, "explode").status_code == 400


def test_siren_unreachable_reports_failure(monkeypatch, caplog):
    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    with caplog.at_level(logging.ERROR, logger="sari_hardware"):
        res = execute_physical_tool("activate_siren", {}, actor=ADMIN)
    assert res["status"] == "failed"
    assert HardwareState.siren_active is False
    assert any(r.levelno >= logging.ERROR for r in caplog.records)
    assert _audit_results() == [("activate_siren", "failed")]


def test_siren_non_2xx_reports_failure(monkeypatch):
    monkeypatch.setattr(hardware.requests, "post", _HttpError())
    res = execute_physical_tool("activate_siren", {}, actor=ADMIN)
    assert res["status"] == "failed"
    assert HardwareState.siren_active is False


def test_failed_deactivate_keeps_siren_active(monkeypatch):
    HardwareState.siren_active = True
    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    res = execute_physical_tool("deactivate_siren", {}, actor=ADMIN)
    assert res["status"] == "failed"
    assert HardwareState.siren_active is True
    assert _audit_results() == [("deactivate_siren", "failed")]


def test_failed_activation_does_not_broadcast(monkeypatch):
    sent = []
    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    monkeypatch.setattr(hardware, "_broadcast", lambda payload: sent.append(payload))
    execute_physical_tool("activate_siren", {}, actor=ADMIN)
    assert sent == []


def test_successful_activation_broadcasts(monkeypatch, siren):
    sent = []
    monkeypatch.setattr(hardware, "_broadcast", lambda payload: sent.append(payload))
    execute_physical_tool("activate_siren", {}, actor=ADMIN)
    assert sent == [{"event": "siren_activated"}]


def test_manual_action_failure_is_reported_to_rest(client, admin_headers, monkeypatch):
    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    res = _manual(client, admin_headers, "activar_sirena")
    assert res.status_code == 200
    assert res.json()["status"] == "failed"


def test_chat_reports_siren_failure(client, admin_headers, monkeypatch):
    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    res = client.post("/api/chat", json={"message": "activa la sirena", "pin": "4321"}, headers=admin_headers)
    assert res.status_code == 200
    assert "He activado" not in res.json()["content"]
    assert HardwareState.siren_active is False


def test_telegram_reports_siren_failure(monkeypatch):
    from app.telegram.bot import handle_telegram_callback

    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    reply = handle_telegram_callback("btn_siren_activate", 111)
    assert "ACTIVADA" not in reply
    assert HardwareState.siren_active is False


def test_gates_are_reported_as_simulated(client, admin_headers, siren):
    res = execute_physical_tool("lock_gates", {}, actor=ADMIN)
    assert "simulat" in res["message"].lower()
    state = client.get("/api/hardware/state", headers=admin_headers).json()
    assert state["gates_simulated"] is True
    assert state["gates_locked"] is True


def test_state_still_reports_siren(client, admin_headers, siren):
    execute_physical_tool("activate_siren", {}, actor=ADMIN)
    state = client.get("/api/hardware/state", headers=admin_headers).json()
    assert state["siren_active"] is True


def test_fake_snapshot_endpoint_is_gone(client, admin_headers):
    assert client.get("/api/hardware/snapshot/<script>", headers=admin_headers).status_code == 404
    assert client.get("/api/hardware/snapshot/cam1").status_code == 404
