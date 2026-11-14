"""Phase B S3, S4, S6, S7: arm/disarm over HTTP, mode-aware alert ingest, timers and the timeline."""
import pytest

from app.domain.alarm import AlarmConfig, ArmMode, ModeConfig, ZoneConfig

KEY = {"X-SARI-Node-Key": "unit-node-key"}
PIN = "4321"
ALERT = {"module_name": "Jetson-PTZ_1", "camara_id": "PTZ_1", "event_type": "intrusion", "severity": "high",
         "message": "Persona en zona norte", "confidence": 0.95}
ACTIVATE = "/api/alarma/activar"
DEACTIVATE = "/api/alarma/desactivar"


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    from app.application import alert_ingest
    from app.ws import manager

    monkeypatch.setattr(alert_ingest, "send_telegram_alert_photo", lambda *a, **k: None)
    monkeypatch.setattr(alert_ingest, "save_event_and_embedding", lambda *a, **k: None)
    monkeypatch.setattr(manager, "broadcast_json", lambda payload: None)


@pytest.fixture
def clock(monkeypatch):
    """Controls the alarm service clock."""
    from app.adapters import composition

    now = {"t": 1_000.0}
    monkeypatch.setattr(composition.alarm, "clock", lambda: now["t"])
    return now


def siren_paths(siren):
    return [c["url"].rsplit(":5000", 1)[-1] for c in siren.calls]


def audit_rows():
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        return [(r.actor_name, r.channel, r.action, r.result) for r in db.query(models.PhysicalActionLog).order_by(models.PhysicalActionLog.id)]
    finally:
        db.close()


def arm(client, headers, mode="away", pin=PIN, **extra):
    return client.post("/api/alarm/arm", json={"mode": mode, "pin": pin, **extra}, headers=headers)


def disarm(client, headers, pin=PIN):
    return client.post("/api/alarm/disarm", json={"pin": pin}, headers=headers)


# -- reading ---------------------------------------------------------------------------------
def test_alarm_status_requires_login(client):
    assert client.get("/api/alarm").status_code == 401


def test_first_status_is_armed_away(client, monitor_headers):
    body = client.get("/api/alarm", headers=monitor_headers).json()
    assert body["state"] == "armed_away"
    assert body["mode"] == "away"
    assert body["deadline"] is None
    assert body["remaining_seconds"] is None
    assert body["faults"] == []


# -- arm / disarm (S4) -------------------------------------------------------------------------
def test_disarm_then_arm_home_with_pin(client, admin_headers, clock):
    res = disarm(client, admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["alarm"]["state"] == "disarmed"

    clock["t"] = 1_010.0
    res = arm(client, admin_headers, "home")
    assert res.status_code == 200, res.text
    assert res.json()["alarm"] == {"state": "armed_home", "mode": "home", "since": 1_010.0, "deadline": None,
                                   "cause": "", "remaining_seconds": None}
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "armed_home"
    assert audit_rows() == [("admin_u", "rest", "alarm_disarm", "success"),
                            ("admin_u", "rest", "alarm_arm_home", "success")]


def test_arm_away_runs_the_exit_delay(client, admin_headers, clock):
    disarm(client, admin_headers)
    body = arm(client, admin_headers, "away").json()["alarm"]
    assert body["state"] == "arming"
    assert body["deadline"] == 1_060.0
    assert body["remaining_seconds"] == 60


def test_wrong_pin_changes_nothing(client, admin_headers):
    assert disarm(client, admin_headers, pin="0000").status_code == 401
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "armed_away"
    assert audit_rows() == []


def test_user_without_hardware_permission_is_denied_and_audited(client, monitor_headers):
    res = disarm(client, monitor_headers)
    assert res.status_code == 403
    assert client.get("/api/alarm", headers=monitor_headers).json()["state"] == "armed_away"
    assert audit_rows() == [("monitor_u", "rest", "alarm_disarm", "denied")]


def test_unknown_mode_is_rejected(client, admin_headers):
    res = arm(client, admin_headers, "vacation")
    assert res.status_code == 400
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "armed_away"


def test_arm_requires_login(client):
    assert client.post("/api/alarm/arm", json={"mode": "away", "pin": PIN}).status_code == 401


def test_node_actor_can_never_disarm():
    from app.adapters.composition import alarm
    from app.domain.actors import Actor

    result = alarm.disarm(Actor.node("Jetson-PTZ_1"))
    assert result["status"] == "denied"
    assert alarm.status().state.value == "armed_away"


# -- alerts by mode (S3) -----------------------------------------------------------------------
def test_alert_while_disarmed_records_but_does_not_sound(client, admin_headers, siren):
    disarm(client, admin_headers)
    siren.calls.clear()
    res = client.post("/api/alerts/event", json=ALERT, headers=KEY)
    assert res.status_code == 200
    assert res.json()["siren_result"] is None
    assert siren.calls == []
    assert res.json()["thread_id"] is not None  # the evidence is still stored
    timeline = client.get("/api/alarm/timeline", headers=admin_headers).json()
    assert timeline[0]["kind"] == "detection_ignored"
    assert timeline[0]["cause"] == "Jetson-PTZ_1"


def test_alert_while_armed_sounds_and_triggers(client, admin_headers, siren, clock):
    res = client.post("/api/alerts/event", json=ALERT, headers=KEY)
    assert res.json()["siren_result"]["status"] == "success"
    assert siren_paths(siren) == [ACTIVATE]
    body = client.get("/api/alarm", headers=admin_headers).json()
    assert body["state"] == "triggered"
    assert body["cause"] == "Jetson-PTZ_1"


def test_alert_during_exit_delay_does_not_sound(client, admin_headers, siren, clock):
    disarm(client, admin_headers)
    arm(client, admin_headers, "away")
    siren.calls.clear()
    assert client.post("/api/alerts/event", json=ALERT, headers=KEY).json()["siren_result"] is None
    assert siren.calls == []


def test_disarm_while_triggered_silences_the_siren(client, admin_headers, siren, clock):
    client.post("/api/alerts/event", json=ALERT, headers=KEY)
    res = disarm(client, admin_headers)
    assert res.status_code == 200
    assert res.json()["siren_result"]["status"] == "success"
    assert siren_paths(siren) == [ACTIVATE, DEACTIVATE]
    assert ("admin_u", "rest", "deactivate_siren", "success") in audit_rows()


def test_cannot_arm_while_triggered(client, admin_headers, siren, clock):
    client.post("/api/alerts/event", json=ALERT, headers=KEY)
    res = arm(client, admin_headers, "home")
    assert res.status_code == 409
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "triggered"


# -- timers run by the worker -----------------------------------------------------------------
def test_exit_delay_completes_on_the_worker_tick(client, admin_headers, clock):
    from app import worker

    disarm(client, admin_headers)
    arm(client, admin_headers, "away")
    clock["t"] = 1_059.0
    worker.maintenance_tick(now=1_059.0)
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "arming"
    clock["t"] = 1_060.0
    worker.maintenance_tick(now=1_060.0)
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "armed_away"


def test_entry_delay_expiry_sounds_the_siren_as_the_system(client, admin_headers, siren, clock, monkeypatch):
    from app import worker
    from app.adapters import composition

    monkeypatch.setattr(composition.alarm, "config", AlarmConfig(
        modes={m: ModeConfig(exit_delay=0, entry_delay=20) for m in ArmMode},
        zones={"perimeter": ZoneConfig(modes=frozenset(ArmMode), immediate=False)},
        trigger_time=30,
    ))
    assert client.post("/api/alerts/event", json=ALERT, headers=KEY).json()["siren_result"] is None
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "pending"
    clock["t"] = 1_020.0
    worker.maintenance_tick(now=1_020.0)
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "triggered"
    assert siren_paths(siren) == [ACTIVATE]
    assert audit_rows()[-1] == ("system:alarm", "system", "activate_siren", "success")


def test_triggered_returns_to_armed_after_trigger_time(client, admin_headers, clock):
    from app import worker

    client.post("/api/alerts/event", json=ALERT, headers=KEY)
    clock["t"] = 1_030.0
    worker.maintenance_tick(now=1_030.0)
    assert client.get("/api/alarm", headers=admin_headers).json()["state"] == "armed_away"


# -- timeline (S6) -------------------------------------------------------------------------------
def test_timeline_lists_transitions_newest_first(client, admin_headers, clock):
    disarm(client, admin_headers)
    clock["t"] = 1_005.0
    arm(client, admin_headers, "night")
    rows = client.get("/api/alarm/timeline", headers=admin_headers).json()
    assert [(r["kind"], r["from_state"], r["to_state"], r["actor"]) for r in rows[:2]] == [
        ("transition", "disarmed", "armed_night", "admin_u"),
        ("transition", "armed_away", "disarmed", "admin_u"),
    ]
    assert rows[0]["at"] == 1_005.0


def test_timeline_requires_login(client):
    assert client.get("/api/alarm/timeline").status_code == 401


# -- fail toward safety (S7) ----------------------------------------------------------------------
def test_alarm_store_down_falls_back_to_the_threshold(client, siren, monkeypatch):
    from app.adapters import composition

    def broken(*a, **k):
        raise RuntimeError("database is down")

    monkeypatch.setattr(composition.alarm.repo, "update", broken)
    monkeypatch.setattr(composition.alarm.repo, "read", broken)
    res = client.post("/api/alerts/event", json=ALERT, headers=KEY)
    assert res.status_code == 200
    assert res.json()["siren_result"]["status"] == "success"
    assert siren_paths(siren) == [ACTIVATE]


def test_weak_alert_never_sounds_even_with_the_store_down(client, siren, monkeypatch):
    from app.adapters import composition

    monkeypatch.setattr(composition.alarm.repo, "update", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    res = client.post("/api/alerts/event", json={**ALERT, "confidence": 0.3}, headers=KEY)
    assert res.json()["siren_result"] is None
    assert siren.calls == []
