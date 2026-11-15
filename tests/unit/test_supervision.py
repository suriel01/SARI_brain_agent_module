"""Phase B S5: heartbeat supervision raises faults (UI, Telegram, timeline), never the siren."""
import time

import pytest

from app.domain.supervision import Heartbeat, evaluate_supervision

KEY = {"X-SARI-Node-Key": "unit-node-key"}
PIN = "4321"


# -- pure rule ---------------------------------------------------------------------------------
def test_stale_heartbeat_raises_and_fresh_one_clears():
    beats = [Heartbeat("node:a", "node", last_seen=80.0, timeout=15),
             Heartbeat("node:b", "node", last_seen=99.0, timeout=15),
             Heartbeat("node:c", "node", last_seen=None, timeout=15)]
    to_raise, to_clear = evaluate_supervision(beats, active={"node:b", "node:gone"}, now=100.0)
    assert [(h.device_id, h.reason) for h in to_raise] == [
        ("node:a", "no heartbeat for 20s (timeout 15s)"), ("node:c", "never reported a heartbeat")]
    assert to_clear == ["node:b", "node:gone"]


def test_already_active_fault_is_not_raised_again():
    beats = [Heartbeat("node:a", "node", last_seen=0.0, timeout=15)]
    assert evaluate_supervision(beats, active={"node:a"}, now=100.0) == ([], [])


def test_timeout_boundary_is_not_a_fault():
    beats = [Heartbeat("node:a", "node", last_seen=85.0, timeout=15)]
    assert evaluate_supervision(beats, active=set(), now=100.0) == ([], [])


# -- supervisor over the real store --------------------------------------------------------------
class Probe:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.ok


@pytest.fixture
def supervisor(monkeypatch):
    from app.adapters import composition
    from app.application.supervision import Supervisor

    sent, events = [], []
    probe = Probe()

    class Broadcast:
        def publish(self, payload, background_tasks=None, *, warn=False):
            events.append(payload)

    sup = Supervisor(repo=composition.alarm.repo, broadcast=Broadcast(), notify=sent.append, siren_health=probe)
    sup.sent, sup.events, sup.probe = sent, events, probe
    monkeypatch.setattr(composition, "supervisor", sup)
    return sup


def timeline(client, headers):
    return client.get("/api/alarm/timeline", headers=headers).json()


def test_silent_registered_node_raises_a_fault_without_the_siren(client, admin_headers, siren, supervisor):
    supervisor.run(["Jetson-PTZ_1"], {"Jetson-PTZ_1": {"last_seen": 1_000.0}}, now=1_000.0)
    assert supervisor.events == []
    result = supervisor.run(["Jetson-PTZ_1"], {"Jetson-PTZ_1": {"last_seen": 1_000.0}}, now=1_020.0)
    assert result.raised == ["node:Jetson-PTZ_1"]
    assert siren.calls == []
    faults = client.get("/api/alarm", headers=admin_headers).json()["faults"]
    assert [(f["device_id"], f["kind"]) for f in faults] == [("node:Jetson-PTZ_1", "node")]
    assert timeline(client, admin_headers)[0]["kind"] == "fault"
    assert supervisor.events[-1]["event"] == "alarm_fault"
    assert supervisor.events[-1]["active"] is True
    assert supervisor.sent == []  # node loss is reported to Telegram by the watchdog's sabotage alert


def test_node_back_clears_the_fault(client, admin_headers, supervisor):
    supervisor.run(["N1"], {}, now=1_000.0)
    result = supervisor.run(["N1"], {"N1": {"last_seen": 1_100.0}}, now=1_101.0)
    assert result.cleared == ["node:N1"]
    assert client.get("/api/alarm", headers=admin_headers).json()["faults"] == []
    assert timeline(client, admin_headers)[0]["kind"] == "fault_cleared"
    assert supervisor.events[-1] == {"event": "alarm_fault", "device_id": "node:N1", "active": False}


def test_unregistered_node_fault_is_cleared(client, admin_headers, supervisor):
    supervisor.run(["N1"], {}, now=1_000.0)
    assert supervisor.run([], {}, now=1_001.0).cleared == ["node:N1"]


def test_siren_service_down_raises_one_fault_and_one_telegram(client, admin_headers, siren, supervisor):
    supervisor.probe.ok = False
    supervisor.run([], {}, now=1_000.0)  # first pass: grace period starts now
    supervisor.run([], {}, now=1_010.0)
    assert supervisor.sent == []
    supervisor.run([], {}, now=1_020.0)
    supervisor.run([], {}, now=1_030.0)
    faults = client.get("/api/alarm", headers=admin_headers).json()["faults"]
    assert [f["device_id"] for f in faults] == ["siren:service"]
    assert len(supervisor.sent) == 1
    assert "siren:service" in supervisor.sent[0]
    assert siren.calls == []

    supervisor.probe.ok = True
    supervisor.run([], {}, now=1_040.0)
    assert client.get("/api/alarm", headers=admin_headers).json()["faults"] == []
    assert len(supervisor.sent) == 2


def test_siren_probe_is_rate_limited(supervisor):
    for t in (1_000.0, 1_002.0, 1_004.0, 1_006.0, 1_008.0, 1_010.0):
        supervisor.run([], {}, now=t)
    assert supervisor.probe.calls == 2


def test_failed_probe_call_counts_as_down(supervisor):
    def boom():
        raise ConnectionError("refused")

    supervisor.siren_health = boom
    supervisor.run([], {}, now=1_000.0)
    supervisor.run([], {}, now=1_020.0)
    assert supervisor.run([], {}, now=1_030.0).raised == [] and supervisor.sent  # raised on the earlier pass


# -- failed to arm (S5) ---------------------------------------------------------------------------
def test_arming_with_an_active_fault_fails_unless_forced(client, admin_headers, supervisor):
    from app.database import SessionLocal
    from app.models import models

    client.post("/api/alarm/disarm", json={"pin": PIN}, headers=admin_headers)
    supervisor.run(["N1"], {}, now=time.time())
    res = client.post("/api/alarm/arm", json={"mode": "home", "pin": PIN}, headers=admin_headers)
    assert res.status_code == 409
    assert res.json()["detail"]["status"] == "failed_to_arm"
    assert res.json()["detail"]["faults"][0]["device_id"] == "node:N1"
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "disarmed"
    assert timeline(client, admin_headers)[0]["kind"] == "failed_to_arm"

    res = client.post("/api/alarm/arm", json={"mode": "home", "pin": PIN, "force": True}, headers=admin_headers)
    assert res.status_code == 200
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "armed_home"
    db = SessionLocal()
    try:
        rows = [(r.action, r.result, r.detail) for r in db.query(models.PhysicalActionLog).order_by(models.PhysicalActionLog.id)]
    finally:
        db.close()
    assert rows[-2][:2] == ("alarm_arm_home", "failed")
    assert rows[-1] == ("alarm_arm_home", "success", "forced with active faults")


# -- worker wiring -------------------------------------------------------------------------------
def test_worker_tick_runs_supervision(client, admin_headers, supervisor, monkeypatch):
    from app import worker

    monkeypatch.setattr(worker, "registered_node_ids", lambda: {"Jetson-PTZ_1"})
    worker.maintenance_tick(now=time.time())
    faults = client.get("/api/alarm", headers=admin_headers).json()["faults"]
    assert [f["device_id"] for f in faults] == ["node:Jetson-PTZ_1"]


# -- watchdog keeps working when the state store is down (Phase A follow-up) ----------------------
@pytest.fixture
def watchdog(monkeypatch):
    from app.telegram import watchdog as wd

    sent = []
    monkeypatch.setattr(wd.telegram_service, "send_telegram_message", lambda text, **k: sent.append(text) or True)
    monkeypatch.setattr(wd, "_last_known", {})

    def one_pass(_seconds):
        wd._watchdog_active = False

    monkeypatch.setattr(wd.time, "sleep", one_pass)

    def run_pass():
        wd._watchdog_active = True
        wd._watchdog_worker()

    wd.sent, wd.run_pass = sent, run_pass
    return wd


def _store_down(monkeypatch):
    from app.adapters import composition

    def down(*a, **k):
        raise RuntimeError("database is down")

    for name in ("list_nodes", "merge_node", "mark_disconnect_notified", "get_node", "add_log", "put_node"):
        monkeypatch.setattr(composition.state, name, down)


def test_watchdog_alerts_from_memory_when_the_store_is_down(watchdog, monkeypatch):
    watchdog.note_heartbeat("W-1", at=time.time() - 20)
    _store_down(monkeypatch)
    watchdog.run_pass()
    watchdog.run_pass()
    assert len(watchdog.sent) == 1
    assert "`W-1`" in watchdog.sent[0]


def test_telemetry_during_an_outage_keeps_the_node_alive(watchdog, monkeypatch):
    from app.mqtt import handlers

    watchdog.note_heartbeat("W-2", at=time.time() - 20)
    _store_down(monkeypatch)
    handlers.handle_telemetry_message("sari/nodes/W-2/telemetry", '{"node_id": "W-2"}')
    watchdog.run_pass()
    assert watchdog.sent == []


def test_watchdog_refreshes_memory_from_the_store(watchdog):
    from app.adapters.composition import state

    state.put_node("W-3", {"node_id": "W-3", "last_seen": time.time() - 20, "is_online": True})
    watchdog.run_pass()
    assert len(watchdog.sent) == 1
    assert watchdog._last_known["W-3"]["is_online"] is False


def test_node_removed_from_the_store_is_forgotten(watchdog):
    watchdog.note_heartbeat("W-4", at=time.time() - 20)
    watchdog.run_pass()  # the store is reachable and does not know W-4
    assert watchdog.sent == []
    assert "W-4" not in watchdog._last_known
