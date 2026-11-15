"""A3 (S5): login/PIN failure counters are shared by every process through the database and survive a restart."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import ratelimit
from app.adapters.persistence.rate_limit_sql import SqlFailureStore


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(ratelimit, "clock", fake)
    return fake


def _sql_store(path):
    from app.main import init_db

    engine = create_engine(f"sqlite:///{path}")
    init_db(bind=engine)
    return SqlFailureStore(sessionmaker(bind=engine)), engine


@pytest.fixture(params=["sql", "memory"])
def store(request, tmp_path):
    if request.param == "memory":
        yield ratelimit.MemoryFailureStore()
        return
    store, engine = _sql_store(tmp_path / "limits.db")
    yield store
    engine.dispose()


def _limiter(store, scope="pin"):
    return ratelimit.FailureLimiter(max_failures=5, window_seconds=900, lockout_seconds=900, scope=scope, store=store)


def test_locks_after_five_failures_and_releases_after_lockout(store, clock):
    lim = _limiter(store)
    for _ in range(4):
        lim.record_failure("k")
    assert lim.is_locked("k") is False
    lim.record_failure("k")
    assert lim.is_locked("k") is True
    clock.now += 899
    assert lim.is_locked("k") is True
    clock.now += 2
    assert lim.is_locked("k") is False


def test_window_is_sliding_not_fixed(store, clock):
    lim = _limiter(store)
    lim.record_failure("k")          # t=1000, leaves the window at t=1900
    clock.now = 1800.0
    for _ in range(3):
        lim.record_failure("k")
    clock.now = 1950.0
    lim.record_failure("k")          # 4 inside the window: not locked
    assert lim.is_locked("k") is False
    lim.record_failure("k")          # 5 inside the window
    assert lim.is_locked("k") is True


def test_lockout_is_seen_by_another_limiter_on_the_same_store(store):
    """Two API workers = two limiter instances over one database."""
    worker_a, worker_b = _limiter(store), _limiter(store)
    for i in range(5):
        (worker_a if i % 2 else worker_b).record_failure("user:7")
    assert worker_a.is_locked("user:7") is True
    assert worker_b.is_locked("user:7") is True


def test_scopes_and_keys_are_isolated_and_reset_is_per_key(store):
    pin, login = _limiter(store, "pin"), _limiter(store, "login")
    for _ in range(5):
        pin.record_failure("k")
        pin.record_failure("other")
    assert login.is_locked("k") is False
    pin.reset("k")
    assert pin.is_locked("k") is False
    assert pin.is_locked("other") is True
    login.record_failure("k")
    pin.clear()
    assert pin.is_locked("other") is False
    assert store.read("login:k")[0] == [1000.0]


def test_scope_clear_treats_like_wildcards_literally(store):
    odd = _limiter(store, "a_")
    neighbour = _limiter(store, "ab")
    for _ in range(5):
        neighbour.record_failure("k")
    odd.clear()
    assert neighbour.is_locked("k") is True


def test_lockout_survives_a_restart(tmp_path):
    path = tmp_path / "limits.db"
    store, engine = _sql_store(path)
    lim = _limiter(store)
    for _ in range(5):
        lim.record_failure("chat:9")
    engine.dispose()

    restarted, engine2 = _sql_store(path)
    assert _limiter(restarted).is_locked("chat:9") is True
    engine2.dispose()


def test_default_limiters_use_the_database():
    assert isinstance(ratelimit.login_limiter._store, SqlFailureStore)
    assert isinstance(ratelimit.pin_limiter._store, SqlFailureStore)
    assert (ratelimit.login_limiter.scope, ratelimit.pin_limiter.scope) == ("login", "pin")
