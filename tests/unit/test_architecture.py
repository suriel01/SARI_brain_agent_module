"""S1: domain stays pure; use cases run on ports; legacy import paths keep working."""
import ast
import pathlib

import pytest

from app.domain.actions import ALL_TOOLS
from app.domain.actors import Actor, has_permission
from app.domain.policy import SIREN_CONFIDENCE_THRESHOLD, should_raise_alarm
from app.domain.state import ActuatorState

DOMAIN = pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "domain"
FORBIDDEN = ("fastapi", "starlette", "pydantic", "sqlalchemy", "requests", "paho", "psycopg2", "alembic", "app")


def _imports(path: pathlib.Path):
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield 0, alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.level, node.module or ""


def test_domain_imports_only_stdlib_and_itself():
    files = sorted(DOMAIN.glob("*.py"))
    assert files, "domain package not found"
    offenders = []
    for path in files:
        for level, module in _imports(path):
            if level > 1 or (level == 0 and module.split(".")[0] in FORBIDDEN and not module.startswith("app.domain")):
                offenders.append(f"{path.name}: {'.' * level}{module}")
    assert offenders == []


def test_purity_scan_catches_a_forbidden_import(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("from ..routers import hardware\nimport sqlalchemy\n")
    assert list(_imports(bad)) == [(2, "routers"), (0, "sqlalchemy")]


@pytest.mark.parametrize("event_type,confidence,expected", [
    ("intrusion", SIREN_CONFIDENCE_THRESHOLD, True),
    ("intrusion", 0.6999, False),
    ("loitering", 1.0, False),
])
def test_should_raise_alarm(event_type, confidence, expected):
    assert should_raise_alarm(event_type, confidence) is expected


def test_should_raise_alarm_honours_a_custom_threshold():
    assert should_raise_alarm("intrusion", 0.5, threshold=0.4) is True
    assert should_raise_alarm("intrusion", 0.5, threshold=0.9) is False


@pytest.mark.parametrize("user", [
    {"role": "admin"},
    {"role": "monitor"},
    {"role": "monitor", "can_control_hardware": True},
    {"role": "monitor", "can_control_hardware": False},
    {},
])
def test_domain_permission_rule_matches_security(user):
    from app.security import has_perm

    assert has_permission(user, "can_control_hardware") == has_perm(user, "can_control_hardware")


def test_routers_hardware_reexports_the_domain_actor():
    from app.routers import hardware

    assert hardware.Actor is Actor
    assert hardware.ALL_TOOLS == ALL_TOOLS


def test_services_alert_ingest_is_the_application_module():
    from app.application import alert_ingest as application_module
    from app.services import alert_ingest as legacy_module

    assert legacy_module is application_module


class _FakeSiren:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def activate(self, duration):
        self.calls.append(("on", duration))
        return (True, "") if self.ok else (False, "boom")

    def deactivate(self):
        self.calls.append(("off", None))
        return (True, "") if self.ok else (False, "boom")


class _FakeState:
    def __init__(self):
        self.siren, self.gates, self.logs = False, False, []

    def actuators(self):
        return ActuatorState(self.siren, self.gates)

    def siren_activated(self, at):
        self.siren = True

    def siren_deactivated(self):
        self.siren = False

    def set_gates_locked(self, locked):
        self.gates = locked

    def add_log(self, msg, level="INFO", camera_module="SYS_CORE"):
        self.logs.append(msg)


def _use_case(siren):
    from app.application.physical_actions import ExecutePhysicalAction

    audit, sent, state = [], [], _FakeState()

    class _Audit:
        def record(self, actor, tool_name, result, detail=""):
            audit.append((tool_name, result))

    class _Broadcast:
        def publish(self, payload, background_tasks=None, *, warn=False):
            sent.append(payload)

    return ExecutePhysicalAction(siren=siren, audit=_Audit(), broadcast=_Broadcast(), state=state, clock=lambda: 1.0), audit, sent, state


def test_use_case_runs_on_fake_ports():
    siren = _FakeSiren()
    run, audit, sent, state = _use_case(siren)
    assert run("activar_sirena", {"duracion_segundos": 5}, actor=Actor("ops", "rest", True))["status"] == "success"
    assert run("deactivate_siren", None, actor=Actor.node("n1"))["status"] == "denied"
    assert siren.calls == [("on", 5)]
    assert state.actuators() == ActuatorState(siren_active=True, gates_locked=False)
    assert audit == [("activar_sirena", "success"), ("deactivate_siren", "denied")]
    assert sent == [{"event": "siren_activated"}]


def test_use_case_failed_actuator_keeps_state_and_does_not_broadcast():
    run, audit, sent, state = _use_case(_FakeSiren(ok=False))
    res = run("activate_siren", {}, actor=Actor("ops", "rest", True))
    assert res == {"status": "failed", "message": "❌ Siren activation failed: boom."}
    assert state.siren is False
    assert sent == []
    assert audit == [("activate_siren", "failed")]


def test_app_code_uses_the_state_repository_not_the_legacy_facade():
    """A2 (S3): live state goes through `composition.state`; `HardwareState` is a test-only facade."""
    app_dir = DOMAIN.parent
    allowed = {app_dir / "adapters" / "state" / "legacy_facade.py", app_dir / "routers" / "hardware.py"}
    offenders = [
        str(path.relative_to(app_dir)) for path in sorted(app_dir.rglob("*.py"))
        if path not in allowed and "HardwareState" in path.read_text()
    ]
    assert offenders == []
    hardware_src = (app_dir / "routers" / "hardware.py").read_text()
    assert "HardwareState." not in hardware_src
