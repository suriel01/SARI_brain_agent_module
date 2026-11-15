"""A3 (S5): realtime events cross processes through PostgreSQL NOTIFY; SQLite keeps in-process delivery."""
import asyncio
import json
import threading

from fastapi import BackgroundTasks

from app.adapters.realtime import ws_broadcast


def test_small_payload_is_sent_verbatim():
    payload = {"event": "siren_activated", "camara_id": "J1", "severity": "high", "thread_id": 3, "snapshot": "data:x"}
    assert json.loads(ws_broadcast.notify_payload(payload)) == payload


def test_oversized_snapshot_is_omitted_and_other_fields_kept():
    payload = {"event": "siren_activated", "camara_id": "J1", "severity": "high", "thread_id": 3,
               "snapshot": "data:image/jpeg;base64," + "A" * 50_000}
    text = ws_broadcast.notify_payload(payload)
    assert len(text.encode()) <= ws_broadcast.NOTIFY_MAX_BYTES
    assert json.loads(text) == {"event": "siren_activated", "camara_id": "J1", "severity": "high", "thread_id": 3,
                                "snapshot": None, "snapshot_omitted": True}


def test_oversized_payload_without_snapshot_keeps_the_event_name():
    text = ws_broadcast.notify_payload({"event": "big", "blob": "é" * 9000})
    assert len(text.encode()) <= ws_broadcast.NOTIFY_MAX_BYTES
    assert json.loads(text) == {"event": "big", "truncated": True}


def test_non_ascii_survives_the_round_trip():
    payload = {"event": "log", "message": "Intrusión ñ 🚨"}
    assert json.loads(ws_broadcast.notify_payload(payload)) == payload


def _postgres_mode(monkeypatch):
    sent = []
    monkeypatch.setattr(ws_broadcast, "uses_postgres", lambda: True)
    monkeypatch.setattr(ws_broadcast, "notify", lambda payload, warn=False: sent.append(payload) or True)
    return sent


def test_on_postgres_events_from_threads_without_a_loop_are_published(monkeypatch):
    """MQTT callbacks and sync endpoints run without an event loop; NOTIFY still publishes them."""
    sent = _postgres_mode(monkeypatch)
    t = threading.Thread(target=ws_broadcast.broadcast, args=({"event": "siren_deactivated"},))
    t.start()
    t.join()
    assert sent == [{"event": "siren_deactivated"}]


def test_on_postgres_background_tasks_publish_after_the_response(monkeypatch):
    sent = _postgres_mode(monkeypatch)
    tasks = BackgroundTasks()
    ws_broadcast.broadcast({"event": "x"}, tasks)
    assert sent == []
    asyncio.run(tasks())
    assert sent == [{"event": "x"}]


def test_sqlite_never_uses_notify(monkeypatch):
    called = []
    monkeypatch.setattr(ws_broadcast, "notify", lambda *a, **k: called.append(a))
    assert ws_broadcast.uses_postgres() is False
    ws_broadcast.broadcast({"event": "x"})
    assert called == []
    assert ws_broadcast.start_listener(asyncio.new_event_loop()) is None


def test_notify_never_raises_when_the_database_fails(monkeypatch):
    class Broken:
        def connect(self):
            raise RuntimeError("down")

    monkeypatch.setattr(ws_broadcast, "_engine", lambda: Broken())
    assert ws_broadcast.notify({"event": "x"}, warn=True) is False


def test_dispatch_delivers_on_the_workers_loop_and_ignores_garbage():
    received = []

    async def deliver(payload):
        received.append(payload)

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    try:
        assert ws_broadcast.dispatch_notification('{"event": "siren_activated"}', loop, deliver) is True
        assert ws_broadcast.dispatch_notification("not json", loop, deliver) is False
        assert ws_broadcast.dispatch_notification("[1, 2]", loop, deliver) is False
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), loop).result(timeout=2)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=2)
    assert received == [{"event": "siren_activated"}]
