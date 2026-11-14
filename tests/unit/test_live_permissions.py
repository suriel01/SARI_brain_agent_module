"""S12: permissions are re-read from the DB on every request."""
from app.crud import crud
from app.database import SessionLocal
from app.routers.hardware import HardwareState


def _update_user(username, **fields):
    db = SessionLocal()
    try:
        user = crud.get_user_by_username(db, username)
        for k, v in fields.items():
            setattr(user, k, v)
        db.commit()
    finally:
        db.close()


def _delete_user(username):
    db = SessionLocal()
    try:
        db.delete(crud.get_user_by_username(db, username))
        db.commit()
    finally:
        db.close()


ACTION = {"action": "activar_sirena", "pin": "4321"}


def test_revoked_hardware_permission_applies_to_existing_token(client, make_user, siren):
    headers = make_user("op", can_control_hardware=True)
    _update_user("op", can_control_hardware=False)
    res = client.post("/api/hardware/manual_action", json=ACTION, headers=headers)
    assert res.status_code == 403
    assert siren.calls == []
    assert HardwareState.siren_active is False


def test_demoted_admin_loses_admin_rights_immediately(client, make_user, siren):
    headers = make_user("boss", role="admin")
    # crud stores every flag as True for admins; demotion clears them, the role no longer implies them.
    _update_user("boss", role="monitor", can_control_hardware=False, can_manage_users=False)
    res = client.post("/api/hardware/manual_action", json=ACTION, headers=headers)
    assert res.status_code == 403
    assert client.get("/api/users/", headers=headers).status_code == 403


def test_granted_permission_applies_to_existing_token(client, make_user, siren):
    headers = make_user("op", can_control_hardware=False)
    _update_user("op", can_control_hardware=True)
    res = client.post("/api/hardware/manual_action", json=ACTION, headers=headers)
    assert res.status_code == 200
    assert HardwareState.siren_active is True


def test_deleted_user_token_is_rejected(client, make_user):
    headers = make_user("gone")
    _delete_user("gone")
    assert client.get("/api/eyes", headers=headers).status_code == 401


def test_deleted_user_cannot_open_websocket(client, make_user):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    headers = make_user("gone")
    token = headers["Authorization"].split(" ", 1)[1]
    _delete_user("gone")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws?token={token}"):
            pass
    assert exc.value.code == 1008


def test_permitted_operator_still_uses_manual_action(client, make_user, siren):
    headers = make_user("op", can_control_hardware=True)
    res = client.post("/api/hardware/manual_action", json=ACTION, headers=headers)
    assert res.status_code == 200
    assert HardwareState.siren_active is True
