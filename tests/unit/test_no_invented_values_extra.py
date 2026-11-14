"""S15 leftovers: eyes list, REST alert ingest and Telegram status never invent values."""
import time

import pytest

from app.routers.hardware import HardwareState


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    from app.services import alert_ingest

    monkeypatch.setattr(alert_ingest, "send_telegram_alert_photo", lambda *a, **k: None)
    monkeypatch.setattr(alert_ingest, "save_event_and_embedding", lambda *a, **k: None)
    HardwareState.nodes.clear()
    yield
    HardwareState.nodes.clear()


def test_eye_without_fps_telemetry_reports_unknown(client, admin_headers):
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    db.add(models.EyeNode(node_id="Jetson-PTZ_1", name="n", ip="10.0.0.5", stream_url="http://10.0.0.5:8080/mjpeg", is_active=True))
    db.commit()
    db.close()
    HardwareState.nodes["Jetson-PTZ_1"] = {"node_id": "Jetson-PTZ_1", "last_seen": time.time(), "is_online": True}
    eyes = client.get("/api/eyes", headers=admin_headers).json()
    node = next(e for e in eyes if e["node_id"] == "Jetson-PTZ_1")
    assert node["fps"] is None
    assert node["link_status"] in (None, "Desconectado")


def test_rest_alert_records_the_caller_ip_not_a_fixed_one(client, siren):
    res = client.post(
        "/api/alerts/event",
        json={"module_name": "Jetson-PTZ_1", "event_type": "intrusion", "message": "x", "confidence": 0.2},
        headers={"X-SARI-Node-Key": "unit-node-key"},
    )
    assert res.status_code == 200
    ips = {n.get("ip") for n in HardwareState.nodes.values()}
    assert "192.168.55.1" not in ips


def test_telegram_status_does_not_invent_fps(monkeypatch):
    from app.telegram import bot

    HardwareState.nodes["Jetson-PTZ_1"] = {"node_id": "Jetson-PTZ_1", "ip": None, "is_online": True, "last_seen": time.time()}
    text = bot.handle_telegram_command("/status", from_chat_id="111")
    assert "30.0 FPS" not in text
