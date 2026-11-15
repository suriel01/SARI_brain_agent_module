"""A hung database must not stall alarm paths, and a failing log write must not break login."""
from app.database import engine_options


def test_postgres_engine_has_a_connect_timeout_but_no_statement_timeout():
    opts = engine_options("postgresql+psycopg2://u:p@db:5432/x")
    assert opts["connect_args"]["connect_timeout"] <= 5
    assert "options" not in opts["connect_args"]  # migrations block on pg_advisory_lock
    assert opts["pool_pre_ping"] is True


def test_sqlite_engine_options_unchanged():
    assert engine_options("sqlite:///./x.db") == {"pool_pre_ping": True}


def test_login_succeeds_when_the_operational_log_write_fails(client, make_user, monkeypatch):
    from app.adapters import composition

    make_user("logger_u")

    def _boom(*args, **kwargs):
        raise RuntimeError("state db down")

    monkeypatch.setattr(composition.state, "add_log", _boom)
    res = client.post("/api/auth/login", json={"username": "logger_u", "password": "pw-unit-test"})
    assert res.status_code == 200
    assert res.json()["access_token"]
