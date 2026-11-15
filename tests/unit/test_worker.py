"""A3 / S4: background work runs in the worker process; the API's /state GET is read-only."""
import threading
import time

from app.adapters.composition import state


def _record_background_starts(monkeypatch):
    from app.mqtt import client as mqtt_client
    from app.telegram import bot, watchdog
    from app import worker

    started = []
    monkeypatch.setattr(mqtt_client, "start_mqtt_client", lambda: started.append("mqtt"))
    monkeypatch.setattr(bot, "start_telegram_bot", lambda: started.append("telegram"))
    monkeypatch.setattr(watchdog, "start_watchdog", lambda: started.append("watchdog"))
    monkeypatch.setattr(worker, "run_scheduler", lambda stop, interval=0: started.append("scheduler"))
    return started


def test_api_startup_does_not_start_background_work_by_default(app, monkeypatch):
    from app import main

    monkeypatch.delenv("SARI_RUN_BACKGROUND", raising=False)
    started = _record_background_starts(monkeypatch)
    main.startup_event()
    assert started == []


def test_api_startup_with_background_flag_also_starts_the_scheduler(app, monkeypatch):
    from app import main, worker

    monkeypatch.setenv("SARI_RUN_BACKGROUND", "true")
    started = _record_background_starts(monkeypatch)
    main.startup_event()
    thread = worker._scheduler_thread
    worker.stop_background_services()
    thread.join(timeout=2)
    assert started == ["mqtt", "telegram", "watchdog", "scheduler"]


def test_api_startup_does_not_write_boot_logs_without_background(app, monkeypatch):
    from app import main

    monkeypatch.delenv("SARI_RUN_BACKGROUND", raising=False)
    main.startup_event()
    assert state.list_logs() == []


def test_state_get_does_not_expire_the_siren_or_prune_nodes(client, admin_headers):
    now = time.time()
    state.overwrite_runtime(siren_active=True, last_alert_time=now - 31)
    state.put_node("ghost", {"node_id": "ghost", "last_seen": now - 61})
    for _ in range(2):
        body = client.get("/api/hardware/state", headers=admin_headers).json()
    assert body["siren_active"] is True
    assert "ghost" in {n["node_id"] for n in body["nodes"]}
    assert state.actuators().siren_active is True
    assert state.get_node("ghost") is not None


def test_maintenance_tick_expires_siren_prunes_ghosts_and_keeps_registered(app):
    from app.database import SessionLocal
    from app.models import models
    from app.worker import maintenance_tick

    db = SessionLocal()
    try:
        db.add(models.EyeNode(node_id="Reg-1", name="r", ip="192.168.1.9", stream_url="http://192.168.1.9/m",
                              yolo_threshold=0.7, is_active=True))
        db.commit()
    finally:
        db.close()
    now = 10_000.0
    state.overwrite_runtime(siren_active=True, last_alert_time=now - 31)
    state.put_node("ghost", {"node_id": "ghost", "last_seen": now - 61})
    state.put_node("Reg-1", {"node_id": "Reg-1", "last_seen": now - 500})
    state.put_node("fresh", {"node_id": "fresh", "last_seen": now - 5})

    result = maintenance_tick(now)

    assert result.siren_expired is True
    assert result.pruned_nodes == ["ghost"]
    assert state.actuators().siren_active is False
    assert sorted(state.list_nodes()) == ["Reg-1", "fresh"]


def test_maintenance_keeps_default_jetson_when_no_eye_is_registered(app):
    from app.worker import maintenance_tick

    now = 10_000.0
    state.put_node("Jetson-PTZ_1", {"node_id": "Jetson-PTZ_1", "last_seen": now - 500})
    maintenance_tick(now)
    assert state.get_node("Jetson-PTZ_1") is not None


def test_scheduler_survives_a_failing_pass(monkeypatch):
    from app import worker

    calls = []
    stop = threading.Event()

    def flaky(now=None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database down")
        stop.set()

    monkeypatch.setattr(worker, "maintenance_tick", flaky)
    worker.run_scheduler(stop, interval=0.01)
    assert len(calls) == 2


def test_worker_main_bootstraps_logs_boot_and_runs_until_stopped(app, monkeypatch):
    from app import main, worker

    started, stopped = [], []
    monkeypatch.setattr(main, "bootstrap_database", lambda: started.append("bootstrap"))
    monkeypatch.setattr(worker, "start_background_services", lambda: started.append("services"))
    monkeypatch.setattr(worker, "stop_background_services", lambda: stopped.append("services"))
    monkeypatch.setattr(worker.signal, "signal", lambda *a: None)

    class _Stop:
        def wait(self, timeout=None):
            return True

    monkeypatch.setattr(worker.threading, "Event", _Stop)
    worker.main()
    assert started == ["bootstrap", "services"]
    assert stopped == ["services"]
    assert state.list_logs()[0]["message"].startswith("🔐 Database reachable")
