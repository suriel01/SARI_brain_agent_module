"""Characterization of the physical-action choke point, alert trigger policy and /state before the hexagonal split (A1).

These pin behaviour that other suites leave implicit, so moving code into domain/application/adapters
cannot change it silently.
"""
import time

import pytest

from app.routers.hardware import Actor, HardwareState, execute_physical_tool

ADMIN = Actor("admin_u", "rest", True)
KEY = {"X-SARI-Node-Key": "unit-node-key"}
ALERT = {"module_name": "Jetson-PTZ_1", "camara_id": "PTZ_1", "event_type": "intrusion", "severity": "high",
         "message": "Persona", "confidence": 0.95}


def _audit():
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        return [(r.actor_name, r.channel, r.action, r.result, r.detail)
                for r in db.query(models.PhysicalActionLog).order_by(models.PhysicalActionLog.id).all()]
    finally:
        db.close()


@pytest.fixture
def ws(monkeypatch):
    """Records every WebSocket payload the backend schedules, from any thread."""
    from app.ws import manager

    sent = []

    async def _record(payload):
        sent.append(payload)

    monkeypatch.setattr(manager, "broadcast_json", _record)
    return sent


@pytest.fixture
def quiet_alerts(monkeypatch):
    from app.services import alert_ingest

    monkeypatch.setattr(alert_ingest, "send_telegram_alert_photo", lambda *a, **k: None)
    monkeypatch.setattr(alert_ingest, "save_event_and_embedding", lambda *a, **k: None)


# --- execute_physical_tool ---------------------------------------------------------------

def test_unknown_tool_is_an_error_audited_as_failed(siren):
    res = execute_physical_tool("open_vault", {}, actor=Actor("admin_u", "rest", True, frozenset({"open_vault"})))
    assert res == {"status": "error", "message": "Unknown hardware tool: open_vault"}
    assert siren.calls == []
    assert _audit() == [("admin_u", "rest", "open_vault", "failed", "Unknown hardware tool: open_vault")]


def test_unlisted_tool_is_denied_even_for_admin(siren):
    res = execute_physical_tool("open_vault", {}, actor=ADMIN)
    assert res["status"] == "denied"
    assert _audit()[0][3] == "denied"


def test_denial_writes_a_warn_log_and_never_calls_the_siren(siren):
    res = execute_physical_tool("activate_siren", {}, actor=Actor("monitor_u", "chat", False))
    assert res == {"status": "denied", "message": "⛔ Permission denied: hardware control not authorized."}
    assert siren.calls == []
    log = HardwareState.logs[0]
    assert log["level"] == "WARN" and log["camera_module"] == "HARDWARE_CTRL"
    assert log["message"] == "⛔ Physical action 'activate_siren' denied for [monitor_u] via chat"
    assert _audit() == [("monitor_u", "chat", "activate_siren", "denied",
                         "⛔ Permission denied: hardware control not authorized.")]


def test_anonymous_denial_log_names_anonymous(siren):
    execute_physical_tool("lock_gates", None, actor=None)
    assert HardwareState.logs[0]["message"] == "⛔ Physical action 'lock_gates' denied for [anonymous] via unknown"


@pytest.mark.parametrize("args,expected", [
    ({}, 30),
    ({"duration_seconds": 12}, 12),
    ({"duracion_segundos": 7}, 7),
    ({"duration_seconds": 0, "duracion_segundos": 9}, 9),
])
def test_activation_request_to_siren_service(siren, args, expected):
    execute_physical_tool("activar_sirena", args, actor=ADMIN)
    assert len(siren.calls) == 1
    call = siren.calls[0]
    assert call["url"] == "http://localhost:5000/api/alarma/activar"
    assert call["json"] == {"duracion": expected}
    assert call["headers"] == {"X-SARI-Siren-Token": "unit-test-siren-token"}
    assert call["timeout"] == 2.0


def test_deactivation_request_has_no_body(siren):
    execute_physical_tool("desactivar_sirena", {}, actor=ADMIN)
    call = siren.calls[0]
    assert call["url"] == "http://localhost:5000/api/alarma/desactivar"
    assert "json" not in call
    assert call["headers"] == {"X-SARI-Siren-Token": "unit-test-siren-token"}


def test_successful_activation_updates_counters_and_log(siren):
    before = time.time()
    res = execute_physical_tool("activate_siren", {"duration_seconds": 15}, actor=ADMIN)
    assert res == {"status": "success", "message": "🚨 Siren activated."}
    assert HardwareState.alert_count == 1
    assert HardwareState.last_alert_time >= before
    log = HardwareState.logs[0]
    assert (log["message"], log["level"], log["camera_module"]) == ("🚨 Physical Siren activated for 15s", "ERROR", "HARDWARE_CTRL")
    assert _audit() == [("admin_u", "rest", "activate_siren", "success", "🚨 Siren activated.")]


def test_failed_activation_leaves_counters_untouched(monkeypatch):
    from app.routers import hardware
    from conftest import SirenRecorder

    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    res = execute_physical_tool("activate_siren", {}, actor=ADMIN)
    assert res == {"status": "failed", "message": "❌ Siren activation failed: siren service unreachable."}
    assert HardwareState.alert_count == 0
    assert HardwareState.logs[0]["message"] == "❌ Siren activation FAILED: siren service unreachable"


def test_deactivation_success_message_and_log(siren):
    HardwareState.siren_active = True
    res = execute_physical_tool("deactivate_siren", {}, actor=ADMIN)
    assert res == {"status": "success", "message": "🔊 Siren turned off & silenced."}
    assert HardwareState.siren_active is False
    assert HardwareState.logs[0]["message"] == "🔊 Siren deactivated / silenced by operator"


@pytest.mark.parametrize("tool,locked,message", [
    ("lock_gates", True, "🔒 Perimeter gates locked (simulated: no gate hardware connected)."),
    ("unlock_gates", False, "🔓 Perimeter gates unlocked (simulated: no gate hardware connected)."),
])
def test_gate_results_are_simulated_and_never_call_the_siren(siren, tool, locked, message):
    HardwareState.gates_locked = not locked
    res = execute_physical_tool(tool, {}, actor=ADMIN)
    assert res == {"status": "success", "simulated": True, "message": message}
    assert HardwareState.gates_locked is locked
    assert siren.calls == []


@pytest.mark.anyio
async def test_broadcast_only_after_confirmed_siren_actions(siren, ws):
    import asyncio

    execute_physical_tool("activate_siren", {}, actor=ADMIN)
    execute_physical_tool("deactivate_siren", {}, actor=ADMIN)
    execute_physical_tool("lock_gates", {}, actor=ADMIN)
    execute_physical_tool("activate_siren", {}, actor=Actor("m", "rest", False))
    await asyncio.sleep(0)
    assert ws == [{"event": "siren_activated"}, {"event": "siren_deactivated"}]


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --- alert trigger policy ------------------------------------------------------------------

@pytest.mark.parametrize("event_type,confidence,raises", [
    ("intrusion", 0.70, True),
    ("intrusion", 0.69, False),
    ("intrusion", 1.0, True),
    ("loitering", 0.99, False),
    ("Intrusion", 0.99, False),
])
def test_rest_alert_siren_threshold(client, siren, admin_headers, quiet_alerts, event_type, confidence, raises):
    body = client.post("/api/alerts/event", json={**ALERT, "event_type": event_type, "confidence": confidence}, headers=KEY).json()
    assert (body["siren_result"] is not None) is raises
    assert (len(siren.calls) == 1) is raises


@pytest.mark.parametrize("event_type,severity,level", [
    ("intrusion", "low", "ERROR"),
    ("loitering", "high", "ERROR"),
    ("loitering", "medium", "WARN"),
    ("loitering", "low", "INFO"),
])
def test_alert_log_level(client, siren, admin_headers, quiet_alerts, event_type, severity, level):
    client.post("/api/alerts/event", json={**ALERT, "event_type": event_type, "severity": severity, "confidence": 0.1}, headers=KEY)
    jetson = [log for log in HardwareState.logs if log["camera_module"] == "JETSON_CV"]
    assert jetson[0]["level"] == level
    assert jetson[0]["message"] == "🚨 [PTZ_1] Persona (Conf: 10%)"


def test_alert_records_node_activity_under_module_name(client, siren, admin_headers, quiet_alerts):
    HardwareState.nodes.pop("PTZ_1", None)
    client.post("/api/alerts/event", json={**ALERT, "confidence": 0.1}, headers=KEY)
    node = HardwareState.nodes["PTZ_1"]
    assert node["name"] == "Jetson Node (PTZ_1)"
    assert node["cpu_load_pct"] is None


# --- /state and /manual_action -------------------------------------------------------------

STATE_KEYS = {"siren_active", "gates_locked", "gates_simulated", "alert_count", "last_alert_thread_id", "logs",
              "nodes", "nodes_count", "system_telemetry"}


def test_state_shape(client, admin_headers):
    body = client.get("/api/hardware/state", headers=admin_headers).json()
    assert set(body) == STATE_KEYS
    assert body["gates_simulated"] is True


def test_state_requires_auth(client):
    assert client.get("/api/hardware/state").status_code == 401


def test_state_turns_siren_off_30s_after_last_alert(client, admin_headers):
    HardwareState.siren_active = True
    HardwareState.last_alert_time = time.time() - 31
    assert client.get("/api/hardware/state", headers=admin_headers).json()["siren_active"] is False
    HardwareState.siren_active = True
    HardwareState.last_alert_time = time.time() - 5
    assert client.get("/api/hardware/state", headers=admin_headers).json()["siren_active"] is True


def test_state_prunes_stale_unregistered_nodes(client, admin_headers):
    now = time.time()
    HardwareState.nodes.clear()
    HardwareState.nodes["ghost"] = {"node_id": "ghost", "last_seen": now - 61}
    HardwareState.nodes["fresh"] = {"node_id": "fresh", "last_seen": now - 5}
    HardwareState.nodes["Jetson-PTZ_1"] = {"node_id": "Jetson-PTZ_1", "last_seen": now - 500}
    try:
        body = client.get("/api/hardware/state", headers=admin_headers).json()
        ids = {n["node_id"]: n for n in body["nodes"]}
        assert set(ids) == {"fresh", "Jetson-PTZ_1"}
        assert ids["fresh"]["is_online"] is True
        assert ids["Jetson-PTZ_1"]["is_online"] is False
        assert body["nodes_count"] == 1
    finally:
        HardwareState.nodes.clear()


def test_manual_action_wrong_pin_is_rejected_without_hardware(client, admin_headers, siren):
    res = client.post("/api/hardware/manual_action", json={"action": "activar_sirena", "pin": "0000"}, headers=admin_headers)
    assert res.status_code == 401
    assert siren.calls == []
    assert _audit() == []


def test_manual_action_denied_detail(client, monitor_headers, siren):
    res = client.post("/api/hardware/manual_action", json={"action": "toggle_sirena", "pin": "4321"}, headers=monitor_headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "Insufficient permissions"
    assert _audit() == [("monitor_u", "rest", "toggle_sirena", "denied", "manual_action without can_control_hardware")]


def test_manual_action_success_body(client, admin_headers, siren):
    res = client.post("/api/hardware/manual_action", json={"action": "cerrar_accesos", "pin": "4321"}, headers=admin_headers)
    assert res.json() == {"status": "success", "simulated": True,
                          "message": "🔒 Perimeter gates locked (simulated: no gate hardware connected)."}
