"""A2 characterization: what each runtime-state consumer shows, pinned before state moved to the database.

Covers the consumers not already pinned elsewhere: Telegram `/status`, the eyes list online flags and
live-node sync, the `/state` counters and log entries, MQTT status transitions and the watchdog
heartbeat timeout.
"""
import time

import pytest

from app.routers.hardware import HardwareState


@pytest.fixture(autouse=True)
def _no_nodes():
    HardwareState.nodes.clear()
    yield
    HardwareState.nodes.clear()


def _eye(node_id, name="Eye", ip="192.168.55.20"):
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        db.add(models.EyeNode(node_id=node_id, name=name, ip=ip, stream_url=f"http://{ip}:8080/mjpeg", is_active=True))
        db.commit()
    finally:
        db.close()


# --- Telegram /status -----------------------------------------------------------------------

def test_telegram_status_reports_actuators_counter_and_nodes():
    from app.telegram import bot

    HardwareState.siren_active = True
    HardwareState.gates_locked = True
    HardwareState.alert_count = 3
    HardwareState.nodes["N-on"] = {"node_id": "N-on", "ip": "10.0.0.9", "fps": 12.5, "is_online": True, "last_seen": time.time()}
    HardwareState.nodes["N-off"] = {"node_id": "N-off", "ip": None, "is_online": False, "last_seen": 0.0}
    text = bot.handle_telegram_command("/status", from_chat_id="111")
    assert "• Sirena Física: 🚨 *ACTIVADA*" in text
    assert "• Accesos Perimetrales: 🔒 *BLOQUEADOS*" in text
    assert "• Total Alertas: `3`" in text
    assert "• `N-on` (🟢 ONLINE): `10.0.0.9` @ 12.5 FPS" in text
    assert "• `N-off` (⚪ STANDBY): `IP desconocida` @ ? FPS" in text


def test_telegram_status_idle_without_nodes():
    from app.telegram import bot

    text = bot.handle_telegram_command("/status", from_chat_id="111")
    assert "🟢 *Inactiva / Silenciada*" in text
    assert "🔓 *Abiertos / Normal*" in text
    assert "• Total Alertas: `0`" in text
    assert "• Ningún nodo registrado" in text


# --- Eyes list online flags -----------------------------------------------------------------

def test_eyes_list_online_flags_follow_live_node_state(client, admin_headers):
    now = time.time()
    for nid in ("E-fresh", "E-stale", "E-down", "E-none"):
        _eye(nid)
    HardwareState.nodes["E-fresh"] = {"node_id": "E-fresh", "last_seen": now - 5, "is_online": True, "fps": 9.0, "link_status": "wifi"}
    HardwareState.nodes["E-stale"] = {"node_id": "E-stale", "last_seen": now - 90, "is_online": True}
    HardwareState.nodes["E-down"] = {"node_id": "E-down", "last_seen": now - 5, "is_online": False}
    eyes = {e["node_id"]: e for e in client.get("/api/eyes", headers=admin_headers).json()}
    assert eyes["E-fresh"]["is_online"] is True
    assert eyes["E-fresh"]["fps"] == 9.0
    assert eyes["E-fresh"]["link_status"] == "wifi"
    for nid in ("E-stale", "E-down", "E-none"):
        assert eyes[nid]["is_online"] is False
        assert eyes[nid]["link_status"] == "Desconectado"
    assert eyes["E-none"]["tracking_enabled"] is True


def test_eye_update_syncs_name_and_ip_into_live_node(client, admin_headers):
    _eye("E-sync", name="old", ip="192.168.55.21")
    HardwareState.nodes["E-sync"] = {"node_id": "E-sync", "name": "old", "ip": "192.168.55.21", "last_seen": time.time(), "is_online": True}
    res = client.put("/api/eyes/E-sync", json={"name": "new", "ip": "192.168.55.22", "pin": "4321"}, headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["is_online"] is True
    assert HardwareState.nodes["E-sync"]["name"] == "new"
    assert HardwareState.nodes["E-sync"]["ip"] == "192.168.55.22"
    assert HardwareState.logs[0]["camera_module"] == "E-sync"


def test_eye_tracking_creates_live_node_entry(client, admin_headers):
    res = client.post("/api/eyes/E-track/tracking", json={"enabled": False}, headers=admin_headers)
    assert res.status_code == 200, res.text
    assert HardwareState.nodes["E-track"] == {"tracking_enabled": False}
    assert HardwareState.logs[0]["message"].endswith("DESACTIVADO para [E-track]")


# --- /state counters and log entries --------------------------------------------------------

def test_state_reports_counters_thread_and_newest_log_first(client, admin_headers):
    HardwareState.alert_count = 4
    HardwareState.last_alert_thread_id = 17
    HardwareState.gates_locked = True
    HardwareState.add_log("first entry", level="INFO", camera_module="T1")
    HardwareState.add_log("second entry", level="WARN", camera_module="T2")
    body = client.get("/api/hardware/state", headers=admin_headers).json()
    assert body["alert_count"] == 4
    assert body["last_alert_thread_id"] == 17
    assert body["gates_locked"] is True
    newest = body["logs"][0]
    assert set(newest) == {"timestamp", "message", "level", "camera_module", "expires_at"}
    assert (newest["message"], newest["level"], newest["camera_module"]) == ("second entry", "WARN", "T2")
    assert body["logs"][1]["message"] == "first entry"


def test_state_node_entries_keep_reported_fields(client, admin_headers):
    HardwareState.nodes["Jetson-PTZ_1"] = {"node_id": "Jetson-PTZ_1", "ip": "10.0.0.7", "fps": 15.0, "last_seen": time.time(), "is_online": True}
    node = client.get("/api/hardware/state", headers=admin_headers).json()["nodes"][0]
    assert node["ip"] == "10.0.0.7"
    assert node["fps"] == 15.0
    assert node["is_online"] is True
    assert node["seconds_since_last_seen"] >= 0


def test_operational_log_keeps_at_most_300_entries():
    for i in range(305):
        HardwareState.add_log(f"entry {i}")
    assert len(HardwareState.logs) <= 300
    assert HardwareState.logs[0]["message"] == "entry 304"


# --- MQTT status transitions ----------------------------------------------------------------

def test_mqtt_status_online_then_offline(monkeypatch):
    from app.mqtt import handlers

    alerts = []
    monkeypatch.setattr(handlers, "trigger_node_disconnection_alert", lambda nid, reason="": alerts.append(nid))
    handlers.handle_status_message("sari/nodes/N-st/status", '{"status": "online", "ip": "10.0.0.31"}')
    node = HardwareState.nodes["N-st"]
    assert node["is_online"] is True and node["ip"] == "10.0.0.31"
    handlers.handle_status_message("sari/nodes/N-st/status", '{"status": "online", "ip": "10.0.0.32"}')
    assert HardwareState.nodes["N-st"]["ip"] == "10.0.0.32"
    handlers.handle_status_message("sari/nodes/N-st/status", '{"status": "offline"}')
    node = HardwareState.nodes["N-st"]
    assert node["is_online"] is False
    assert node["last_seen"] == 0.0
    assert alerts == ["N-st"]
    assert HardwareState.logs[0]["level"] == "WARNING"


# --- Watchdog heartbeat timeout -------------------------------------------------------------

def test_watchdog_marks_silent_online_node_offline_and_alerts_once(monkeypatch):
    from app.telegram import watchdog

    sent = []
    monkeypatch.setattr(watchdog.telegram_service, "send_telegram_message", lambda text, **k: sent.append(text) or True)
    monkeypatch.setattr(watchdog, "_disconnected_nodes_notified", set())
    now = time.time()
    HardwareState.nodes["W-silent"] = {"node_id": "W-silent", "ip": "10.0.0.40", "last_seen": now - 20, "is_online": True}
    HardwareState.nodes["W-fresh"] = {"node_id": "W-fresh", "last_seen": now, "is_online": True}
    HardwareState.nodes["W-off"] = {"node_id": "W-off", "last_seen": now - 100, "is_online": False}

    def one_pass(_seconds):
        watchdog._watchdog_active = False

    monkeypatch.setattr(watchdog.time, "sleep", one_pass)
    watchdog._watchdog_active = True
    watchdog._watchdog_worker()

    assert HardwareState.nodes["W-silent"]["is_online"] is False
    assert HardwareState.nodes["W-fresh"]["is_online"] is True
    assert len(sent) == 1 and "`W-silent`" in sent[0] and "`10.0.0.40`" in sent[0]
    assert HardwareState.logs[0]["level"] == "ERROR"
    assert HardwareState.logs[0]["camera_module"] == "W-silent"
