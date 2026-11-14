import pytest

from app.config import ConfigError, load_settings

VALID = {
    "SARI_SECRET_KEY": "x" * 40,
    "SARI_SECURITY_PIN": "8642",
    "MQTT_USER": "brain",
    "MQTT_PASSWORD": "a-strong-broker-password",
}


@pytest.fixture
def env(monkeypatch):
    for k, v in VALID.items():
        monkeypatch.setenv(k, v)
    return monkeypatch


def test_valid_settings_load(env):
    s = load_settings()
    assert s.secret_key == "x" * 40
    assert s.security_pin == "8642"
    assert s.token_expire_minutes == 60


@pytest.mark.parametrize("name", list(VALID))
def test_missing_secret_fails_closed(env, name):
    env.delenv(name)
    with pytest.raises(ConfigError, match=name):
        load_settings()


@pytest.mark.parametrize(
    "name,value",
    [
        ("SARI_SECRET_KEY", "SARI_SUPER_SECRET_KEY"),
        ("SARI_SECURITY_PIN", "1234"),
        ("MQTT_PASSWORD", "sari_secure_password_2026"),
    ],
)
def test_known_leaked_defaults_are_rejected(env, name, value):
    env.setenv(name, value)
    with pytest.raises(ConfigError):
        load_settings()


def test_short_secret_key_rejected(env):
    env.setenv("SARI_SECRET_KEY", "short")
    with pytest.raises(ConfigError, match="at least"):
        load_settings()


def test_non_numeric_pin_rejected(env):
    env.setenv("SARI_SECURITY_PIN", "abcd")
    with pytest.raises(ConfigError, match="digits"):
        load_settings()


def _seed_eye(node_id="Jetson-PTZ_1"):
    from app.database import SessionLocal
    from app.models import models

    db = SessionLocal()
    try:
        db.add(models.EyeNode(node_id=node_id, name="n", ip="10.0.0.5", stream_url="http://10.0.0.5:8080/mjpeg"))
        db.commit()
    finally:
        db.close()


def test_eye_update_without_pin_is_rejected(client, admin_headers):
    _seed_eye()
    res = client.put("/api/eyes/Jetson-PTZ_1", json={"name": "renamed"}, headers=admin_headers)
    assert res.status_code == 401


def test_eye_update_with_configured_pin_succeeds(client, admin_headers):
    _seed_eye()
    res = client.put("/api/eyes/Jetson-PTZ_1", json={"name": "renamed", "pin": "4321"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "renamed"


def test_admin_seed_requires_bootstrap_password(app, monkeypatch):
    from app import main

    monkeypatch.delenv("SARI_ADMIN_PASSWORD", raising=False)
    with pytest.raises(ConfigError, match="SARI_ADMIN_PASSWORD"):
        main.seed_initial_data()
