"""T14: REST and MQTT alert ingest share one pipeline; each transport keeps its observable behaviour."""
import json

import pytest

from app.routers.hardware import HardwareState

KEY = {"X-SARI-Node-Key": "unit-node-key"}
SNAP = "QUJD"  # raw base64, normalised to a data URL by both transports


@pytest.fixture
def captured(monkeypatch):
    """Captures Telegram, WebSocket and embedding side effects wherever the pipeline lives."""
    import importlib

    from app.ws import manager

    out = {"telegram": [], "ws": [], "embedding": []}

    def _tg(snapshot, caption=None, reply_markup=None, **kw):
        out["telegram"].append({"snapshot": snapshot, "caption": caption, "reply_markup": reply_markup})

    def _emb(module_name, desc, conf):
        out["embedding"].append((module_name, desc, conf))

    targets = ["app.routers.alerts", "app.mqtt.handlers"]
    try:
        importlib.import_module("app.services.alert_ingest")
        targets.append("app.services.alert_ingest")
    except ImportError:
        pass
    for mod_name in targets:
        mod = importlib.import_module(mod_name)
        monkeypatch.setattr(mod, "send_telegram_alert_photo", _tg, raising=False)
        monkeypatch.setattr(mod, "save_event_and_embedding", _emb, raising=False)
    monkeypatch.setattr(manager, "broadcast_json", lambda payload: out["ws"].append(payload))
    return out


def _thread_messages(thread_id):
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        thread = db.get(models.ChatThread, thread_id)
        return thread.title, [(m.role, m.content, m.snapshot) for m in sorted(thread.messages, key=lambda m: m.id)]
    finally:
        db.close()


def _audit():
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        return [(r.actor_name, r.channel, r.action, r.result) for r in db.query(models.PhysicalActionLog).all()]
    finally:
        db.close()


ALERT = {"module_name": "Jetson-PTZ_1", "camara_id": "PTZ_1", "event_type": "intrusion", "severity": "high",
         "message": "Persona en zona norte", "confidence": 0.95, "image_base64": SNAP}


# --- REST characterization ----------------------------------------------------------------

def test_rest_intrusion_full_pipeline(client, siren, admin_headers, captured):
    res = client.post("/api/alerts/event", json=ALERT, headers=KEY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"status", "thread_id", "evidence_log", "siren_result", "has_snapshot"}
    assert body["status"] == "success"
    assert body["has_snapshot"] is True
    assert body["siren_result"]["status"] == "success"
    assert body["evidence_log"].startswith("⚠️ ALERTA DE EVIDENCIA DESDE MÓDULO JETSON [")
    assert "• Dispositivo: PTZ_1" in body["evidence_log"]
    assert "• Tipo: intrusion (high)" in body["evidence_log"]
    assert "• Confianza CV: 95%" in body["evidence_log"]

    title, msgs = _thread_messages(body["thread_id"])
    assert title == "🚨 [EVIDENCIA] PTZ_1"
    assert msgs[0] == ("system", body["evidence_log"], f"data:image/jpeg;base64,{SNAP}")
    assert msgs[1][1].startswith("🔊 Respuesta física iniciada")
    assert HardwareState.last_alert_thread_id == body["thread_id"]
    assert HardwareState.siren_active is True
    assert HardwareState.logs[0]["camera_module"] in ("HARDWARE_CTRL", "JETSON_CV")
    assert any(log["camera_module"] == "JETSON_CV" and "Persona en zona norte" in log["message"] and log["level"] == "ERROR"
               for log in HardwareState.logs)

    assert len(captured["telegram"]) == 1
    tg = captured["telegram"][0]
    assert tg["snapshot"] == f"data:image/jpeg;base64,{SNAP}"
    assert "`PTZ_1`" in tg["caption"] and "`HIGH`" in tg["caption"] and "`95%`" in tg["caption"]
    assert [b["callback_data"] for row in tg["reply_markup"]["inline_keyboard"] for b in row] == [
        "btn_siren_activate", "btn_gates_lock", "btn_silence", "btn_status"]

    assert captured["ws"] == [{"event": "siren_activated", "camara_id": "PTZ_1", "severity": "high",
                               "thread_id": body["thread_id"], "snapshot": f"data:image/jpeg;base64,{SNAP}"}]
    assert captured["embedding"] == [("PTZ_1", "Persona en zona norte", 0.95)]
    assert _audit() == [("node:Jetson-PTZ_1", "node", "activate_siren", "success")]


def test_rest_reuses_thread_for_same_module(client, siren, admin_headers, captured):
    first = client.post("/api/alerts/event", json=ALERT, headers=KEY).json()["thread_id"]
    second = client.post("/api/alerts/event", json={**ALERT, "confidence": 0.2}, headers=KEY).json()["thread_id"]
    assert first == second


def test_rest_low_confidence_no_siren(client, siren, admin_headers, captured):
    body = client.post("/api/alerts/event", json={**ALERT, "confidence": 0.5}, headers=KEY).json()
    assert body["siren_result"] is None
    assert siren.calls == []
    assert captured["ws"] == []
    assert len(captured["telegram"]) == 1
    _, msgs = _thread_messages(body["thread_id"])
    assert len(msgs) == 1


def test_rest_confidence_from_metadata_and_default(client, siren, admin_headers, captured):
    alert = {k: v for k, v in ALERT.items() if k != "confidence"}
    body = client.post("/api/alerts/event", json={**alert, "metadata": {"confidence": 0.81}}, headers=KEY).json()
    assert "• Confianza CV: 81%" in body["evidence_log"]
    body = client.post("/api/alerts/event", json={**alert, "metadata": {}, "image_base64": None}, headers=KEY).json()
    assert "• Confianza CV: 90%" in body["evidence_log"]
    assert body["has_snapshot"] is False


def test_rest_non_intrusion_logs_at_lower_level(client, siren, admin_headers, captured):
    client.post("/api/alerts/event", json={**ALERT, "event_type": "loitering", "severity": "medium"}, headers=KEY)
    assert siren.calls == []
    assert any(log["camera_module"] == "JETSON_CV" and log["level"] == "WARN" for log in HardwareState.logs)


def test_rest_siren_failure_is_not_announced(client, admin_headers, captured, monkeypatch):
    from app.routers import hardware
    from conftest import SirenRecorder

    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    body = client.post("/api/alerts/event", json=ALERT, headers=KEY).json()
    assert body["siren_result"]["status"] == "failed"
    assert captured["ws"] == []
    _, msgs = _thread_messages(body["thread_id"])
    assert not any(c.startswith("🔊 Respuesta física iniciada") for _, c, _ in msgs)


# --- MQTT characterization ----------------------------------------------------------------

def _mqtt(payload: dict):
    from app.mqtt.handlers import handle_alert_message

    handle_alert_message(json.dumps(payload))


def _latest_thread_id():
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        return db.query(models.ChatThread).order_by(models.ChatThread.id.desc()).first().id
    finally:
        db.close()


def test_mqtt_intrusion_full_pipeline(siren, admin_headers, captured):
    HardwareState.nodes.pop("PTZ_1", None)
    _mqtt({**ALERT, "image_base64": None, "snapshot": SNAP, "ip": "192.168.55.7"})
    thread_id = _latest_thread_id()
    title, msgs = _thread_messages(thread_id)
    assert title == "🚨 [EVIDENCIA] PTZ_1"
    assert msgs[0][1].startswith("⚠️ ALERTA DE EVIDENCIA DESDE MÓDULO JETSON (MQTT) [")
    assert "• Dispositivo: PTZ_1" in msgs[0][1]
    assert msgs[0][2] == f"data:image/jpeg;base64,{SNAP}"
    assert msgs[1][1].startswith("🔊 Respuesta física iniciada")
    assert HardwareState.last_alert_thread_id == thread_id
    assert HardwareState.siren_active is True
    assert HardwareState.nodes["PTZ_1"]["ip"] == "192.168.55.7"
    assert len(captured["telegram"]) == 1
    assert "`PTZ_1`" in captured["telegram"][0]["caption"]
    assert captured["embedding"] == []  # MQTT path never stored an embedding
    assert _audit() == [("node:PTZ_1", "node", "activate_siren", "success")]


def test_mqtt_low_confidence_no_siren(siren, admin_headers, captured):
    _mqtt({**ALERT, "confidence": 0.4})
    assert siren.calls == []
    _, msgs = _thread_messages(_latest_thread_id())
    assert len(msgs) == 1


def test_mqtt_bad_payload_is_swallowed(siren, captured):
    from app.mqtt.handlers import handle_alert_message

    handle_alert_message("{not json")
    assert siren.calls == []
    assert captured["telegram"] == []


def test_mqtt_siren_failure_is_not_announced(admin_headers, captured, monkeypatch):
    from app.routers import hardware
    from conftest import SirenRecorder

    monkeypatch.setattr(hardware.requests, "post", SirenRecorder(fail=True))
    _mqtt(ALERT)
    _, msgs = _thread_messages(_latest_thread_id())
    assert not any(c.startswith("🔊 Respuesta física iniciada") for _, c, _ in msgs)


def test_both_transports_share_one_pipeline():
    import inspect

    from app.mqtt import handlers
    from app.routers import alerts

    for mod in (alerts, handlers):
        src = inspect.getsource(mod)
        assert "ingest_alert(" in src
        assert "inline_keyboard" not in src
