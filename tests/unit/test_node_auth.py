"""S6: machine endpoints require a per-node key."""
import pytest

from app.routers.hardware import HardwareState

KEY = {"X-SARI-Node-Key": "unit-node-key"}
ALERT = {"module_name": "Jetson-PTZ_1", "camara_id": "PTZ_1", "event_type": "intrusion", "message": "Persona", "confidence": 0.95}
ALERT_PATHS = [
    "/api/alerts/event", "/api/alerts/event/", "/api/alert/event", "/api/alerts/alerta", "/api/alerts/",
    "/api/event", "/alerts/event", "/api/alerts/alerts/event",
]


@pytest.fixture(autouse=True)
def _no_telegram(monkeypatch):
    from app.routers import alerts

    monkeypatch.setattr(alerts, "send_telegram_alert_photo", lambda *a, **k: None)
    monkeypatch.setattr(alerts, "save_event_and_embedding", lambda *a, **k: None)


@pytest.mark.parametrize("path", ALERT_PATHS)
def test_alert_without_key_is_rejected(client, siren, path):
    res = client.post(path, json=ALERT)
    assert res.status_code == 401
    assert siren.calls == []
    assert HardwareState.siren_active is False


def test_alert_with_wrong_key_is_rejected(client, siren):
    res = client.post("/api/alerts/event", json=ALERT, headers={"X-SARI-Node-Key": "nope"})
    assert res.status_code == 401
    assert siren.calls == []


def test_alert_with_valid_key_triggers_siren(client, siren, admin_headers):
    res = client.post("/api/alerts/event", json=ALERT, headers=KEY)
    assert res.status_code == 200, res.text
    assert res.json()["siren_result"]["status"] == "success"
    assert HardwareState.siren_active is True
    assert len(siren.calls) == 1


def test_low_confidence_alert_does_not_trigger_siren(client, siren, admin_headers):
    res = client.post("/api/alerts/event", json={**ALERT, "confidence": 0.3}, headers=KEY)
    assert res.status_code == 200
    assert siren.calls == []


def test_alert_history_requires_user(client, admin_headers):
    assert client.get("/api/alerts/event").status_code in (401, 403)
    assert client.get("/api/alerts/event", headers=admin_headers).status_code == 200


TELEMETRY = {"node_id": "Jetson-PTZ_1", "ip": "10.0.0.5", "cpu_load_pct": 10.0}


def test_telemetry_without_key_is_rejected(client):
    assert client.post("/api/hardware/telemetry/node", json=TELEMETRY).status_code == 401
    assert client.post("/api/telemetry/node", json=TELEMETRY).status_code == 401


def test_telemetry_for_another_node_is_forbidden(client):
    res = client.post("/api/hardware/telemetry/node", json={**TELEMETRY, "node_id": "Jetson-PTZ_9"}, headers=KEY)
    assert res.status_code == 403
    assert "Jetson-PTZ_9" not in HardwareState.nodes


def test_telemetry_with_valid_key_is_recorded(client):
    res = client.post("/api/hardware/telemetry/node", json=TELEMETRY, headers=KEY)
    assert res.status_code == 200
    assert HardwareState.nodes["Jetson-PTZ_1"]["cpu_load_pct"] == 10.0


def test_node_keys_parsing(monkeypatch):
    from app.node_auth import parse_node_keys

    assert parse_node_keys("a:k1, b:k2") == {"k1": "a", "k2": "b"}
    assert parse_node_keys("") == {}
    with pytest.raises(ValueError):
        parse_node_keys("a:k1,b:k1")
    with pytest.raises(ValueError):
        parse_node_keys("broken")
