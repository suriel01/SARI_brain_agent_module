"""T14: chat snapshot/status fast-rails report real data, never fabricated values."""
import time

from app.routers.hardware import HardwareState

FABRICATED = ["192.168.1.73", "192.168.1.74", "96.4%", "PERSON DETECTED", "RECORDING", "GRABANDO"]


def _chat(client, headers, message, language="es"):
    res = client.post("/api/chat", json={"message": message, "pin": "4321", "language": language}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _seed_event(module="PTZ_1"):
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        db.add(models.EventLog(module_name=module, event_description="Persona", confidence=0.8))
        db.commit()
    finally:
        db.close()


def test_status_report_has_no_hardcoded_values(client, admin_headers):
    _seed_event()
    for lang in ("es", "en"):
        content = _chat(client, admin_headers, "estado del sistema" if lang == "es" else "system status", lang)["content"]
        for fake in FABRICATED:
            assert fake not in content, (lang, fake)


def test_status_report_uses_live_node_telemetry(client, admin_headers):
    HardwareState.nodes["Jetson-Live"] = {"node_id": "Jetson-Live", "ip": "10.0.0.42", "last_seen": time.time(), "is_online": True}
    HardwareState.nodes["Jetson-Gone"] = {"node_id": "Jetson-Gone", "ip": "10.0.0.43", "last_seen": 0.0, "is_online": False}
    try:
        content = _chat(client, admin_headers, "system status", "en")["content"]
    finally:
        HardwareState.nodes.pop("Jetson-Live", None)
        HardwareState.nodes.pop("Jetson-Gone", None)
    live_row = next(line for line in content.splitlines() if "Jetson-Live" in line)
    gone_row = next(line for line in content.splitlines() if "Jetson-Gone" in line)
    assert "10.0.0.42" in live_row and "ONLINE" in live_row
    assert "OFFLINE" in gone_row


def test_status_report_still_reports_siren_and_gates(client, admin_headers):
    """Previous behaviour: the status fast-rail reports the actuator state."""
    HardwareState.siren_active = True
    content = _chat(client, admin_headers, "estado del sistema")["content"]
    assert "ACTIVADA" in content
    assert "simulado" in content.lower()


def test_snapshot_reply_has_no_fabricated_detection(client, admin_headers):
    content = _chat(client, admin_headers, "ver camara")["content"]
    for fake in FABRICATED:
        assert fake not in content
    assert "/api/hardware/snapshot" not in content


def test_snapshot_reply_attaches_latest_real_evidence(client, admin_headers):
    from app.crud import crud
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        thread = crud.create_thread(db, user_id=1, title="🚨 [EVIDENCIA] PTZ_1")
        crud.add_message(db, thread.id, role="system", content="evidence PTZ_1", snapshot="data:image/jpeg;base64,QUJD")
    finally:
        db.close()
    body = _chat(client, admin_headers, "take snapshot", "en")
    assert body["snapshot"] == "data:image/jpeg;base64,QUJD"
