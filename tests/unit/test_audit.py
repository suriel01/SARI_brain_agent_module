"""S8: every physical action is persisted with actor, channel, action, result and timestamp."""
import pytest

from app.routers.hardware import Actor, HardwareState, execute_physical_tool

NODE_KEY = {"X-SARI-Node-Key": "unit-node-key"}
ALERT = {"module_name": "Jetson-PTZ_1", "camara_id": "PTZ_1", "event_type": "intrusion", "message": "Persona", "confidence": 0.95}


def _rows():
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        rows = db.query(models.PhysicalActionLog).order_by(models.PhysicalActionLog.id.asc()).all()
        return [(r.actor_name, r.channel, r.action, r.result) for r in rows], rows
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _no_side_channels(monkeypatch):
    from app.services import alert_ingest as alerts

    monkeypatch.setattr(alerts, "send_telegram_alert_photo", lambda *a, **k: None)
    monkeypatch.setattr(alerts, "save_event_and_embedding", lambda *a, **k: None)


def test_success_is_audited_with_utc_timestamp(siren):
    execute_physical_tool("activate_siren", {}, actor=Actor("admin_u", "rest", True))
    summary, rows = _rows()
    assert summary == [("admin_u", "rest", "activate_siren", "success")]
    assert rows[0].timestamp is not None


def test_denied_is_audited(siren):
    execute_physical_tool("lock_gates", {}, actor=Actor("monitor_u", "rest", False))
    assert _rows()[0] == [("monitor_u", "rest", "lock_gates", "denied")]


def test_anonymous_denial_is_audited(siren):
    execute_physical_tool("activate_siren", {}, actor=None)
    assert _rows()[0] == [("anonymous", "unknown", "activate_siren", "denied")]


def test_rest_manual_action_is_audited(client, admin_headers, siren):
    res = client.post("/api/hardware/manual_action", json={"action": "toggle_sirena", "pin": "4321"}, headers=admin_headers)
    assert res.status_code == 200
    assert _rows()[0] == [("admin_u", "rest", "activate_siren", "success")]


def test_rest_manual_action_denied_for_monitor_is_audited(client, monitor_headers, siren):
    res = client.post("/api/hardware/manual_action", json={"action": "activar_sirena", "pin": "4321"}, headers=monitor_headers)
    assert res.status_code == 403
    assert _rows()[0] == [("monitor_u", "rest", "activate_siren", "denied")]


def test_chat_fast_rail_success_and_denial_are_audited(client, make_user, admin_headers, siren):
    client.post("/api/chat", json={"message": "activa la sirena", "pin": "4321"}, headers=admin_headers)
    monitor = make_user("chatter", role="monitor", can_create_chats=True)
    client.post("/api/chat", json={"message": "bloquear accesos", "pin": "4321"}, headers=monitor)
    assert _rows()[0] == [("admin_u", "chat", "activate_siren", "success"), ("chatter", "chat", "lock_gates", "denied")]


def test_node_alert_is_audited(client, siren):
    res = client.post("/api/alerts/event", json=ALERT, headers=NODE_KEY)
    assert res.status_code == 200
    assert _rows()[0] == [("node:Jetson-PTZ_1", "node", "activate_siren", "success")]


def test_telegram_button_is_audited(siren):
    from app.telegram.bot import handle_telegram_callback

    handle_telegram_callback("btn_siren_activate", 111)
    assert _rows()[0] == [("telegram:111", "telegram", "activate_siren", "success")]


def test_audit_db_failure_does_not_block_the_alarm(monkeypatch, siren):
    from app.routers import hardware

    class _Broken:
        def __call__(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(hardware, "SessionLocal", _Broken())
    res = execute_physical_tool("activate_siren", {}, actor=Actor("admin_u", "rest", True))
    assert res["status"] == "success"
    assert HardwareState.siren_active is True
    assert len(siren.calls) == 1


def test_audit_endpoint_lists_newest_first(client, admin_headers, siren):
    execute_physical_tool("activate_siren", {}, actor=Actor("admin_u", "rest", True))
    execute_physical_tool("lock_gates", {}, actor=Actor("ops", "chat", True))
    res = client.get("/api/hardware/audit?limit=1", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["actor_name"] == "ops"
    assert body[0]["action"] == "lock_gates"
    assert body[0]["result"] == "success"
    assert set(body[0]) >= {"id", "timestamp", "actor_name", "channel", "action", "result", "detail"}


def test_audit_endpoint_caps_limit(client, admin_headers):
    assert client.get("/api/hardware/audit?limit=100000", headers=admin_headers).status_code == 200


def test_audit_endpoint_forbidden_for_monitor(client, monitor_headers):
    assert client.get("/api/hardware/audit", headers=monitor_headers).status_code == 403


def test_audit_endpoint_requires_login(client):
    assert client.get("/api/hardware/audit").status_code in (401, 403)
