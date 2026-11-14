"""The choke point must not fail after the hardware already acted when the state store is down."""
import pytest

from app.application.physical_actions import ExecutePhysicalAction
from app.domain.actors import Actor


class _BrokenState:
    def __getattr__(self, name):
        def _boom(*args, **kwargs):
            raise RuntimeError("state db down")
        return _boom


class _Siren:
    def __init__(self):
        self.calls = []

    def activate(self, duration):
        self.calls.append(("on", duration))
        return True, ""

    def deactivate(self):
        self.calls.append(("off", None))
        return True, ""


class _Audit:
    def __init__(self):
        self.rows = []

    def record(self, actor, tool, result, detail):
        self.rows.append((tool, result))


class _Broadcast:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event["event"])


@pytest.fixture
def parts():
    siren, audit, broadcast = _Siren(), _Audit(), _Broadcast()
    use_case = ExecutePhysicalAction(siren=siren, audit=audit, broadcast=broadcast, state=_BrokenState())
    return use_case, siren, audit, broadcast


OPERATOR = Actor("admin_u", "rest", True)


@pytest.mark.parametrize("tool,event", [("activate_siren", "siren_activated"), ("deactivate_siren", "siren_deactivated")])
def test_siren_action_reports_success_and_is_audited_when_state_store_fails(parts, tool, event):
    use_case, siren, audit, broadcast = parts
    res = use_case(tool, {}, actor=OPERATOR)
    assert res["status"] == "success"
    assert res["state_persisted"] is False
    assert len(siren.calls) == 1
    assert audit.rows == [(tool, "success")]
    assert broadcast.events == [event]


def test_gate_action_reports_success_and_is_audited_when_state_store_fails(parts):
    use_case, _, audit, _ = parts
    res = use_case("lock_gates", {}, actor=OPERATOR)
    assert res["status"] == "success"
    assert res["state_persisted"] is False
    assert audit.rows == [("lock_gates", "success")]


def test_denial_is_audited_when_state_store_fails(parts):
    use_case, siren, audit, _ = parts
    res = use_case("activate_siren", {}, actor=Actor("monitor_u", "rest", False))
    assert res["status"] == "denied"
    assert siren.calls == []
    assert audit.rows == [("activate_siren", "denied")]
