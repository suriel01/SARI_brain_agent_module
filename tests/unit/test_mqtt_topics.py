"""T11 (S13): MQTT alerts are bound to the node named in the topic; the legacy shared topic is opt-out."""
import json

import pytest

from app.routers.hardware import HardwareState

SNAP = "QUJD"
ALERT = {"module_name": "Jetson-PTZ_1", "camara_id": "PTZ_1", "event_type": "intrusion", "severity": "high",
         "message": "Persona en zona norte", "confidence": 0.95, "snapshot": SNAP, "ip": "192.168.55.7"}


@pytest.fixture(autouse=True)
def quiet_side_effects(monkeypatch):
    from app.services import alert_ingest
    from app.ws import manager

    monkeypatch.setattr(alert_ingest, "send_telegram_alert_photo", lambda *a, **kw: None)
    monkeypatch.setattr(manager, "broadcast_json", lambda payload: None)


def _audit():
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        return [(r.actor_name, r.channel, r.action, r.result) for r in db.query(models.PhysicalActionLog).all()]
    finally:
        db.close()


def _route(topic, payload, legacy_alerts=True):
    from app.mqtt.handlers import route_message

    route_message(topic, json.dumps(payload) if isinstance(payload, dict) else payload, legacy_alerts=legacy_alerts)


def test_node_alert_topic_binds_actor_to_topic_node(siren, admin_headers):
    # The payload claims another node; the actor must be the node the broker authenticated (topic).
    _route("sari/nodes/Jetson-PTZ_2/alerts", {**ALERT, "camara_id": "Jetson-PTZ_1", "module_name": "Jetson-PTZ_1"})
    assert _audit() == [("node:Jetson-PTZ_2", "node", "activate_siren", "success")]
    assert HardwareState.siren_active is True


def test_node_alert_topic_works_with_legacy_disabled(siren, admin_headers):
    _route("sari/nodes/Jetson-PTZ_1/alerts", ALERT, legacy_alerts=False)
    assert _audit() == [("node:Jetson-PTZ_1", "node", "activate_siren", "success")]


def test_legacy_topic_still_raises_alarm_when_enabled(siren, admin_headers):
    # Previous behaviour: sari/alerts triggers the siren as the node named in the payload.
    _route("sari/alerts", ALERT, legacy_alerts=True)
    assert _audit() == [("node:PTZ_1", "node", "activate_siren", "success")]


def test_legacy_topic_ignored_when_disabled(siren, admin_headers):
    _route("sari/alerts", ALERT, legacy_alerts=False)
    assert siren.calls == []
    assert _audit() == []
    assert HardwareState.siren_active is False


@pytest.mark.parametrize("topic", ["sari/nodes//alerts", "sari/nodes/a/b/alerts", "sari/nodes/+/alerts", "sari/x/n1/alerts"])
def test_malformed_alert_topics_are_ignored(siren, admin_headers, topic):
    _route(topic, ALERT)
    assert siren.calls == []
    assert _audit() == []


def test_telemetry_and_status_routing_unchanged(admin_headers):
    HardwareState.nodes.pop("n-telem", None)
    _route("sari/nodes/n-telem/telemetry", {"fps": 12.0})
    assert HardwareState.nodes["n-telem"]["fps"] == 12.0
    _route("sari/nodes/n-telem/status", {"status": "offline"})
    assert HardwareState.nodes["n-telem"]["is_online"] is False


def test_subscriptions_follow_legacy_flag():
    from app.mqtt.client import subscriptions

    with_legacy = dict(subscriptions(legacy_alerts=True))
    assert with_legacy == {"sari/nodes/+/telemetry": 0, "sari/nodes/+/status": 1, "sari/nodes/+/alerts": 1, "sari/alerts": 1}
    assert "sari/alerts" not in dict(subscriptions(legacy_alerts=False))


def test_legacy_alerts_setting_defaults_to_true(monkeypatch):
    from app.config import load_settings

    monkeypatch.delenv("SARI_MQTT_LEGACY_ALERTS", raising=False)
    assert load_settings().mqtt_legacy_alerts is True
    monkeypatch.setenv("SARI_MQTT_LEGACY_ALERTS", "false")
    assert load_settings().mqtt_legacy_alerts is False
