"""A3 review advisory: a database failure during alert ingest never stops the siren (fail open)."""
import json

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

KEY = {"X-SARI-Node-Key": "unit-node-key"}
ALERT = {"module_name": "Jetson-PTZ_1", "camara_id": "PTZ_1", "event_type": "intrusion", "severity": "high",
         "message": "Persona en zona norte", "confidence": 0.95, "image_base64": "QUJD"}


@pytest.fixture
def side_effects(monkeypatch):
    import importlib

    out = {"telegram": [], "embedding": []}
    for name in ("app.routers.alerts", "app.mqtt.handlers", "app.application.alert_ingest"):
        mod = importlib.import_module(name)
        monkeypatch.setattr(mod, "send_telegram_alert_photo", lambda s, caption=None, reply_markup=None, **k:
                            out["telegram"].append(caption), raising=False)
        monkeypatch.setattr(mod, "save_event_and_embedding", lambda *a: out["embedding"].append(a), raising=False)
    return out


@pytest.fixture
def database_down(monkeypatch):
    """Every ORM statement, flush and commit fails, as when PostgreSQL is unreachable."""

    def fail(*_a, **_k):
        raise OperationalError("SELECT 1", {}, Exception("could not connect to server"))

    def activate():
        for name in ("execute", "flush", "commit", "get", "scalar", "scalars"):
            monkeypatch.setattr(Session, name, fail)

    return activate


def _activations(siren):
    return [c for c in siren.calls if c["url"].endswith("/api/alarma/activar")]


def test_mqtt_alert_sounds_the_siren_when_the_database_is_down(app, siren, side_effects, database_down):
    from app.mqtt import handlers

    database_down()
    handlers.handle_alert_message(json.dumps({**ALERT, "image_base64": None}), node_id="Jetson-PTZ_1")
    assert len(_activations(siren)) == 1
    assert len(side_effects["telegram"]) == 1


def test_rest_alert_sounds_the_siren_when_the_database_is_down(client, siren, side_effects, database_down):
    database_down()
    res = client.post("/api/alerts/event", json=ALERT, headers=KEY)
    assert len(_activations(siren)) == 1
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["siren_result"]["status"] == "success"
    assert body["thread_id"] is None
    assert "• Confianza CV: 95%" in body["evidence_log"]


def test_low_confidence_alert_with_database_down_still_does_not_sound(client, siren, side_effects, database_down):
    database_down()
    res = client.post("/api/alerts/event", json={**ALERT, "confidence": 0.5}, headers=KEY)
    assert res.status_code == 200
    assert _activations(siren) == []
