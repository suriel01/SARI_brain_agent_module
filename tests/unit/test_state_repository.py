"""A2 (S3): the StateRepository contract, shared by the SQL (production) and memory (dev/test) adapters,
and persistence of live state across a process restart."""
import datetime
import threading
import time

import pytest
from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import sessionmaker

from app.adapters.persistence.state_sql import SqlStateRepository
from app.adapters.state.memory_state import MemoryState
from app.domain.state import LOG_CAPACITY, NODE_TELEMETRY_FIELDS, RuntimeState
from app.models.models import OperationalLog


def _migrated_engine(path):
    from app.main import init_db

    engine = create_engine(f"sqlite:///{path}")
    init_db(bind=engine)
    return engine


@pytest.fixture(params=["sql", "memory"])
def repo(request, tmp_path):
    if request.param == "memory":
        yield MemoryState()
        return
    engine = _migrated_engine(tmp_path / "state.db")
    repository = SqlStateRepository(sessionmaker(bind=engine))
    repository.engine = engine
    yield repository
    engine.dispose()


def _expire_all_logs(repo):
    past = datetime.datetime.now() - datetime.timedelta(seconds=1)
    if isinstance(repo, MemoryState):
        for entry in repo._logs:
            entry["expires_at"] = past
        return
    with repo.engine.begin() as conn:
        conn.execute(update(OperationalLog).values(expires_at=past))


def test_initial_state_is_all_off(repo):
    assert repo.snapshot() == RuntimeState()
    assert repo.list_nodes() == {}
    assert repo.list_logs() == []


def test_siren_activation_sets_flag_counter_and_time(repo):
    repo.siren_activated(100.0)
    repo.siren_activated(200.0)
    snap = repo.snapshot()
    assert (snap.siren_active, snap.alert_count, snap.last_alert_time) == (True, 2, 200.0)
    repo.siren_deactivated()
    assert repo.snapshot().siren_active is False
    assert repo.snapshot().alert_count == 2


def test_concurrent_activations_never_lose_an_increment(repo):
    threads = [threading.Thread(target=repo.siren_activated, args=(float(i),)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert repo.snapshot().alert_count == 20


def test_gates_and_last_thread(repo):
    repo.set_gates_locked(True)
    repo.set_last_alert_thread(42)
    snap = repo.snapshot()
    assert snap.gates_locked is True and snap.last_alert_thread_id == 42
    assert repo.actuators().gates_locked is True


def test_expire_siren_only_after_the_window(repo):
    repo.siren_activated(1000.0)
    assert repo.expire_siren(1029.0, 30) is False
    assert repo.snapshot().siren_active is True
    assert repo.expire_siren(1031.0, 30) is True
    assert repo.snapshot().siren_active is False
    assert repo.expire_siren(2000.0, 30) is False


def test_overwrite_runtime_rejects_unknown_fields(repo):
    repo.overwrite_runtime(alert_count=7, siren_active=True)
    assert repo.snapshot().alert_count == 7
    with pytest.raises(AttributeError):
        repo.overwrite_runtime(bogus=1)


def test_record_node_activity_creates_unknown_telemetry_then_refreshes(repo):
    repo.record_node_activity("n1")
    node = repo.get_node("n1")
    assert node["ip"] is None and all(node[f] is None for f in NODE_TELEMETRY_FIELDS)
    repo.merge_node("n1", {"last_seen": 1.0})
    repo.record_node_activity("n1", ip="10.0.0.8")
    node = repo.get_node("n1")
    assert node["ip"] == "10.0.0.8" and node["last_seen"] > 1.0
    repo.record_node_activity("n1")
    assert repo.get_node("n1")["ip"] == "10.0.0.8"


def test_put_merge_remove_and_list_nodes(repo):
    repo.put_node("b", {"node_id": "b", "fps": 12.0})
    repo.put_node("a", {"node_id": "a"})
    assert list(repo.list_nodes()) == ["a", "b"]
    assert repo.merge_node("b", {"is_online": False}) is True
    assert repo.get_node("b") == {"node_id": "b", "fps": 12.0, "is_online": False}
    assert repo.merge_node("ghost", {"x": 1}) is False
    assert repo.get_node("ghost") is None
    assert repo.merge_node("t", {"tracking_enabled": True}, create=True) is True
    assert repo.get_node("t") == {"tracking_enabled": True}
    repo.put_node("b", {"node_id": "b"})
    assert repo.get_node("b") == {"node_id": "b"}
    repo.remove_node("a")
    assert "a" not in repo.list_nodes()
    repo.clear_nodes()
    assert repo.list_nodes() == {}


def test_prune_nodes_keeps_registered_and_fresh(repo):
    now = time.time()
    repo.put_node("ghost", {"last_seen": now - 61})
    repo.put_node("blank", {"node_id": "blank"})
    repo.put_node("fresh", {"last_seen": now - 5})
    repo.put_node("registered", {"last_seen": now - 500})
    removed = repo.prune_nodes(now - 60, keep={"registered"})
    assert sorted(removed) == ["blank", "ghost"]
    assert sorted(repo.list_nodes()) == ["fresh", "registered"]


def test_logs_are_newest_first_with_the_api_shape(repo):
    repo.add_log("first", level="INFO", camera_module="T1")
    repo.add_log("second", level="WARN", camera_module="T2")
    logs = repo.list_logs()
    assert [log["message"] for log in logs] == ["second", "first"]
    assert set(logs[0]) == {"timestamp", "message", "level", "camera_module", "expires_at"}
    assert (logs[0]["level"], logs[0]["camera_module"]) == ("WARN", "T2")
    stamp = datetime.datetime.strptime(logs[0]["timestamp"], "%Y-%m-%d %H:%M:%S")
    expires = datetime.datetime.strptime(logs[0]["expires_at"], "%Y-%m-%d %H:%M:%S")
    assert expires - stamp == datetime.timedelta(hours=24)
    assert [log["message"] for log in repo.list_logs(limit=1)] == ["second"]


def test_log_is_capped(repo):
    for i in range(LOG_CAPACITY + 5):
        repo.add_log(f"entry {i}")
    logs = repo.list_logs()
    assert len(logs) == LOG_CAPACITY
    assert logs[0]["message"] == f"entry {LOG_CAPACITY + 4}"
    assert logs[-1]["message"] == "entry 5"


def test_expired_logs_are_hidden_and_purged(repo):
    repo.add_log("old")
    _expire_all_logs(repo)
    assert repo.list_logs() == []
    repo.add_log("new")
    assert [log["message"] for log in repo.list_logs()] == ["new"]
    repo.purge_expired_logs()
    assert [log["message"] for log in repo.list_logs()] == ["new"]


def test_migration_seeds_the_single_actuator_row(tmp_path):
    engine = _migrated_engine(tmp_path / "seed.db")
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, siren_active, alert_count FROM actuator_state")).all()
        assert rows == [(1, 0, 0)]
    finally:
        engine.dispose()


def test_state_survives_a_restart(tmp_path):
    """Written through one engine, read back by a brand-new engine and repository (simulated restart)."""
    path = tmp_path / "restart.db"
    engine = _migrated_engine(path)
    before = SqlStateRepository(sessionmaker(bind=engine))
    before.siren_activated(123.0)
    before.set_gates_locked(True)
    before.set_last_alert_thread(9)
    before.put_node("Jetson-PTZ_1", {"node_id": "Jetson-PTZ_1", "ip": "10.0.0.7", "fps": 15.0, "last_seen": 50.0})
    before.add_log("persisted entry", level="WARN", camera_module="T1")
    engine.dispose()

    engine = create_engine(f"sqlite:///{path}")
    try:
        after = SqlStateRepository(sessionmaker(bind=engine))
        assert after.snapshot() == RuntimeState(siren_active=True, gates_locked=True, alert_count=1,
                                                last_alert_time=123.0, last_alert_thread_id=9)
        assert after.get_node("Jetson-PTZ_1")["fps"] == 15.0
        assert after.list_logs()[0]["message"] == "persisted entry"
    finally:
        engine.dispose()


def test_app_composition_uses_the_sql_repository():
    from app.adapters import composition

    assert isinstance(composition.state, SqlStateRepository)
    assert composition.physical_action.state is composition.state
