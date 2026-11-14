"""S4: every physical action goes through one permission-checked choke point."""
import asyncio

import pytest

from app.routers import hardware
from app.routers.hardware import Actor, HardwareState, execute_physical_tool


def test_actor_is_required():
    with pytest.raises(TypeError):
        execute_physical_tool("activate_siren", {})


@pytest.mark.parametrize("tool", ["activate_siren", "deactivate_siren", "lock_gates", "unlock_gates"])
def test_actor_without_permission_is_denied(siren, tool):
    HardwareState.siren_active = tool == "deactivate_siren"
    before = (HardwareState.siren_active, HardwareState.gates_locked)
    actor = Actor(name="monitor_u", channel="rest", can_control_hardware=False)
    res = execute_physical_tool(tool, {}, actor=actor)
    assert res["status"] == "denied"
    assert siren.calls == []
    assert (HardwareState.siren_active, HardwareState.gates_locked) == before


def test_permitted_actor_activates_siren(siren):
    res = execute_physical_tool("activate_siren", {}, actor=Actor("admin_u", "rest", True))
    assert res["status"] == "success"
    assert HardwareState.siren_active is True
    assert len(siren.calls) == 1


def test_node_actor_may_only_raise_the_alarm(siren):
    node = Actor.node("Jetson-PTZ_1")
    assert execute_physical_tool("activate_siren", {}, actor=node)["status"] == "success"
    for tool in ("deactivate_siren", "lock_gates", "unlock_gates"):
        assert execute_physical_tool(tool, {}, actor=node)["status"] == "denied"
    assert HardwareState.siren_active is True


def test_actor_from_user_maps_permissions():
    assert Actor.from_user({"username": "a", "role": "admin"}, "rest").can_control_hardware is True
    assert Actor.from_user({"username": "m", "role": "monitor"}, "rest").can_control_hardware is False
    assert Actor.from_user({"username": "m", "role": "monitor", "can_control_hardware": True}, "rest").can_control_hardware


def _run(coro):
    return asyncio.run(coro)


def test_llm_action_without_actor_context_is_denied(siren):
    from app.routers import chat

    msg = _run(chat.action_activate_siren())
    assert "denied" in msg.lower() or "denegad" in msg.lower()
    assert siren.calls == []
    assert HardwareState.siren_active is False


@pytest.mark.parametrize(
    "fn,state_attr",
    [("action_activate_siren", "siren_active"), ("action_lock_gates", "gates_locked")],
)
def test_llm_action_respects_monitor_permissions(siren, fn, state_attr):
    from app.routers import chat

    token = chat.current_actor.set(Actor("monitor_u", "llm", False))
    try:
        _run(getattr(chat, fn)())
    finally:
        chat.current_actor.reset(token)
    assert getattr(HardwareState, state_attr) is False
    assert siren.calls == []


def test_llm_deactivate_denied_for_monitor(siren):
    from app.routers import chat

    HardwareState.siren_active = True
    token = chat.current_actor.set(Actor("monitor_u", "llm", False))
    try:
        _run(chat.action_deactivate_siren())
    finally:
        chat.current_actor.reset(token)
    assert HardwareState.siren_active is True


def test_llm_action_allowed_for_operator(siren):
    from app.routers import chat

    token = chat.current_actor.set(Actor("admin_u", "llm", True))
    try:
        _run(chat.action_activate_siren())
    finally:
        chat.current_actor.reset(token)
    assert HardwareState.siren_active is True


def test_monitor_cannot_use_manual_action(client, monitor_headers, siren):
    res = client.post("/api/hardware/manual_action", json={"action": "activar_sirena", "pin": "4321"}, headers=monitor_headers)
    assert res.status_code == 403
    assert siren.calls == []


def test_monitor_chat_siren_request_is_denied(client, make_user, siren):
    headers = make_user("chatter", role="monitor", can_create_chats=True)
    res = client.post("/api/chat", json={"message": "activa la sirena", "pin": "4321"}, headers=headers)
    assert res.status_code == 200
    assert HardwareState.siren_active is False
    assert siren.calls == []


def test_mcp_tools_go_through_choke_point(monkeypatch, siren):
    import app.sari_mcp_server as mcp_srv

    monkeypatch.setenv("SARI_MCP_HARDWARE_ENABLED", "false")
    assert "denied" in mcp_srv.activate_siren().lower()
    assert siren.calls == []
    monkeypatch.setenv("SARI_MCP_HARDWARE_ENABLED", "true")
    mcp_srv.activate_siren()
    assert HardwareState.siren_active is True
    assert hardware.HardwareState.siren_active is True
