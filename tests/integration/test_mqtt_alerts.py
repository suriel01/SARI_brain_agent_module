import os
import json
import time
import pytest
import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "sari-mqtt")
BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", 1883))
BROKER_USER = os.environ.get("MQTT_USER", "sari_operator")
BROKER_PASS = os.environ.get("MQTT_PASSWORD", "sari_secure_password_2026")

def test_mqtt_alert_ingestion_and_db_persistence():
    from app.database import SessionLocal
    from app.models import models
    from app.routers.hardware import HardwareState

    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test_jetson_alert_pub")
    pub.username_pw_set(BROKER_USER, BROKER_PASS)
    pub.connect(BROKER_HOST, BROKER_PORT, 60)

    test_snapshot = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    alert_payload = {
        "camara_id": "Jetson-PTZ_ALERT_TEST",
        "event_type": "intrusion",
        "confidence": 0.94,
        "message": "Intruso detectado en perímetro norte por YOLO",
        "severity": "high",
        "snapshot": test_snapshot,
        "ip": "192.168.1.150"
    }

    info = pub.publish("sari/alerts", json.dumps(alert_payload), qos=1)
    info.wait_for_publish(timeout=2.0)
    time.sleep(0.3)
    pub.disconnect()

    # Wait up to 3 seconds for backend handler to process and commit to DB
    db = SessionLocal()
    found_message = None
    start = time.time()
    try:
        while time.time() - start < 4.0:
            thread = db.query(models.ChatThread).filter(
                models.ChatThread.title.ilike("%Jetson-PTZ_ALERT_TEST%")
            ).order_by(models.ChatThread.id.desc()).first()

            if thread:
                msg = db.query(models.ChatMessage).filter(
                    models.ChatMessage.thread_id == thread.id,
                    models.ChatMessage.snapshot.isnot(None)
                ).order_by(models.ChatMessage.id.desc()).first()
                if msg:
                    found_message = msg
                    break
            time.sleep(0.3)
    finally:
        db.close()

    assert found_message is not None, "Alert with snapshot should be stored in database"
    assert test_snapshot in found_message.snapshot, "Snapshot data should be saved in ChatMessage.snapshot"
    assert "Intruso detectado" in found_message.content, "Content should include alert message"
    # Check running backend API for siren status and hardware log
    import urllib.request
    login_req = urllib.request.Request(
        "http://127.0.0.1:7000/api/auth/login",
        data=json.dumps({"username": "admin", "password": "sari_password"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req, timeout=3.0) as l_resp:
        token = json.loads(l_resp.read().decode())["access_token"]

    hw_req = urllib.request.Request(
        "http://127.0.0.1:7000/api/hardware/state",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(hw_req, timeout=3.0) as h_resp:
        hw_state = json.loads(h_resp.read().decode())
    
    assert hw_state.get("siren_active") is True, f"Hardware siren should be active in backend, got: {hw_state}"
    logs = [l["message"] for l in hw_state.get("logs", [])]
    assert any("Jetson-PTZ_ALERT_TEST" in m for m in logs), f"Log for alert should be present in hardware logs: {logs}"
    print("[+] test_mqtt_alert_ingestion_and_db_persistence passed successfully!")

if __name__ == "__main__":
    test_mqtt_alert_ingestion_and_db_persistence()
