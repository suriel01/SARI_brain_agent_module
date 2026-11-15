"""Unit-test harness: SQLite, no broker, no Telegram, siren HTTP calls recorded instead of sent."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="sari-unit-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/sari_unit.db"
os.environ["SARI_SECRET_KEY"] = "unit-test-secret-key-0123456789abcdef"
os.environ["SARI_SECURITY_PIN"] = "4321"
os.environ["MQTT_USER"] = "brain-unit"
os.environ["MQTT_PASSWORD"] = "unit-broker-password"
os.environ["SARI_ADMIN_PASSWORD"] = "unit-admin-bootstrap"
os.environ["SARI_SIREN_TOKEN"] = "unit-test-siren-token"
os.environ["SARI_NODE_KEYS"] = "Jetson-PTZ_1:unit-node-key"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = "111"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TEST_PIN = "4321"
NODE_KEY = "unit-node-key"


@pytest.fixture(scope="session")
def app():
    from app import main

    main.init_db()
    return main.app


@pytest.fixture(autouse=True)
def clean_state(app, monkeypatch):
    from app.database import engine
    from app.models import models

    # Live state (actuators, counters, nodes, operational log) lives in these tables too, so this
    # resets it along with every other table.
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    from app import ratelimit
    from app.adapters import composition

    ratelimit.reset_all()
    # Process-local alarm memory (ignored-detection rate limit, owed entry-delay siren) per test.
    monkeypatch.setattr(composition.alarm, "_ignored_logged", {})
    monkeypatch.setattr(composition.alarm, "_siren_owed", False)
    yield


class SirenRecorder:
    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    def __call__(self, url, *args, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.fail:
            raise ConnectionError("siren service unreachable")

        class _Resp:
            status_code = 200

            def json(self):
                return {"status": "ok"}

        return _Resp()


@pytest.fixture
def siren(monkeypatch):
    from app.routers import hardware

    recorder = SirenRecorder()
    monkeypatch.setattr(hardware.requests, "post", recorder)
    return recorder


@pytest.fixture
def client(app, siren):
    return TestClient(app)


@pytest.fixture
def make_user(client):
    def _make(username: str, role: str = "monitor", password: str = "pw-unit-test", **perms):
        from app.crud import crud
        from app.database import SessionLocal
        from app.schemas import schemas

        db = SessionLocal()
        try:
            crud.create_user(
                db,
                schemas.UserCreate(username=username, password=password, role=role, clearance_level=1, **perms),
            )
        finally:
            db.close()
        res = client.post("/api/auth/login", json={"username": username, "password": password})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _make


@pytest.fixture
def admin_headers(make_user):
    return make_user("admin_u", role="admin")


@pytest.fixture
def monitor_headers(make_user):
    """Monitor with no hardware permission."""
    return make_user("monitor_u", role="monitor")
