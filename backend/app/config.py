"""Central runtime settings. Secrets have no defaults: the backend refuses to start without them."""
import os
from dataclasses import dataclass
from functools import lru_cache

MIN_SECRET_KEY_LENGTH = 32
KNOWN_INSECURE_VALUES = {"SARI_SUPER_SECRET_KEY", "sari_secure_password_2026", "sari_password", "1234", "changeme"}


class ConfigError(RuntimeError):
    """Raised when required security settings are missing or insecure."""


@dataclass(frozen=True)
class Settings:
    secret_key: str
    security_pin: str
    token_expire_minutes: int
    mqtt_host: str
    mqtt_port: int
    mqtt_user: str
    mqtt_password: str
    siren_token: str
    mqtt_legacy_alerts: bool = True


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required setting {name}")
    if value in KNOWN_INSECURE_VALUES:
        raise ConfigError(f"Setting {name} uses a known insecure default value")
    return value


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    secret_key = _required("SARI_SECRET_KEY")
    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise ConfigError(f"SARI_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters")

    pin = _required("SARI_SECURITY_PIN")
    if not pin.isdigit() or len(pin) < 4:
        raise ConfigError("SARI_SECURITY_PIN must be at least 4 digits")

    return Settings(
        secret_key=secret_key,
        security_pin=pin,
        token_expire_minutes=int(os.environ.get("SARI_TOKEN_EXPIRE_MINUTES", "60")),
        mqtt_host=os.environ.get("MQTT_BROKER_HOST", "sari-mqtt"),
        mqtt_port=int(os.environ.get("MQTT_BROKER_PORT", "1883")),
        mqtt_user=_required("MQTT_USER"),
        mqtt_password=_required("MQTT_PASSWORD"),
        siren_token=_required("SARI_SIREN_TOKEN"),
        # Transitional: the shared `sari/alerts` topic cannot prove which node sent an alert.
        mqtt_legacy_alerts=_flag("SARI_MQTT_LEGACY_ALERTS", default=True),
    )


def run_background() -> bool:
    """True when this process must run MQTT, Telegram polling, the watchdog and the scheduler.

    Only `python -m app.worker` (or single-process development) sets SARI_RUN_BACKGROUND=true;
    API workers leave it unset so background work never runs twice.
    """
    return _flag("SARI_RUN_BACKGROUND", default=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
