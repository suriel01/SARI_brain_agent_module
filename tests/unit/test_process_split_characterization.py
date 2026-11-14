"""Characterization before the A3 process split: startup background work, the broadcast helper,
the watchdog debounce and the tracking override. Pinned on the single-process code first."""
import asyncio
import logging
import time

from fastapi import BackgroundTasks

from app.adapters.composition import state

# --- startup starts the background services ----------------------------------------------------

def _record_background_starts(monkeypatch):
    from app.mqtt import client as mqtt_client
    from app.telegram import bot, watchdog

    started = []
    monkeypatch.setattr(mqtt_client, "start_mqtt_client", lambda: started.append("mqtt"))
    monkeypatch.setattr(bot, "start_telegram_bot", lambda: started.append("telegram"))
    monkeypatch.setattr(watchdog, "start_watchdog", lambda: started.append("watchdog"))
    return started


def test_startup_with_background_enabled_starts_mqtt_telegram_and_watchdog(app, monkeypatch):
    from app import main

    monkeypatch.setenv("SARI_RUN_BACKGROUND", "true")
    started = _record_background_starts(monkeypatch)
    main.startup_event()
    assert started == ["mqtt", "telegram", "watchdog"]


# --- broadcast helper (in-process delivery) ----------------------------------------------------

def test_broadcast_with_background_tasks_sends_after_the_response(monkeypatch):
    from app.adapters.realtime import ws_broadcast
    from app.ws import manager

    sent = []

    async def _send(payload):
        sent.append(payload)

    monkeypatch.setattr(manager, "broadcast_json", _send)
    tasks = BackgroundTasks()
    ws_broadcast.broadcast({"event": "x"}, tasks)
    assert sent == []
    asyncio.run(tasks())
    assert sent == [{"event": "x"}]


def test_broadcast_inside_a_running_loop_is_delivered(monkeypatch):
    from app.adapters.realtime import ws_broadcast
    from app.ws import manager

    sent = []

    async def _send(payload):
        sent.append(payload)

    monkeypatch.setattr(manager, "broadcast_json", _send)

    async def _main():
        ws_broadcast.broadcast({"event": "y"})
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_main())
    assert sent == [{"event": "y"}]


# --- watchdog debounce ----------------------------------------------------------------------

def test_disconnection_alert_is_debounced_until_the_node_reports_again(monkeypatch):
    from app.mqtt import handlers
    from app.telegram import watchdog

    sent = []
    monkeypatch.setattr(watchdog.telegram_service, "send_telegram_message", lambda text, **k: sent.append(text) or True)
    assert watchdog.trigger_node_disconnection_alert("D-1") is True
    assert watchdog.trigger_node_disconnection_alert("D-1") is False
    handlers.handle_telemetry_message("sari/nodes/D-1/telemetry", '{"fps": 10}')
    assert watchdog.trigger_node_disconnection_alert("D-1") is True
    assert len(sent) == 2


# --- tracking override survives telemetry ---------------------------------------------------

def test_tracking_choice_survives_a_telemetry_overwrite(client, admin_headers):
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        db.add(models.EyeNode(node_id="T-eye", name="Tracking eye", ip="192.168.1.20",
                              stream_url="http://192.168.1.20:8080/mjpeg", yolo_threshold=0.7, is_active=True))
        db.commit()
    finally:
        db.close()

    assert client.post("/api/eyes/T-eye/tracking", json={"enabled": False}, headers=admin_headers).status_code == 200
    # Telemetry replaces the node's data (as the MQTT handler and /telemetry/node do).
    state.put_node("T-eye", {"node_id": "T-eye", "fps": 12.0, "last_seen": time.time(), "is_online": True})
    assert "tracking_enabled" not in state.get_node("T-eye")
    eye = next(e for e in client.get("/api/eyes", headers=admin_headers).json() if e["node_id"] == "T-eye")
    assert eye["tracking_enabled"] is False


def test_broadcast_outside_a_loop_is_dropped_and_logged_when_asked(monkeypatch, caplog):
    import threading

    from app.adapters.realtime import ws_broadcast
    from app.ws import manager

    sent = []
    monkeypatch.setattr(manager, "broadcast_json", lambda payload: sent.append(payload))
    with caplog.at_level(logging.WARNING, logger="sari_realtime"):
        t = threading.Thread(target=ws_broadcast.broadcast, args=({"event": "z"},), kwargs={"warn": True})
        t.start()
        t.join()
    assert sent == []
    assert any("Could not broadcast" in r.message for r in caplog.records)
