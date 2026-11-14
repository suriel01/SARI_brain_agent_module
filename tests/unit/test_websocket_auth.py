"""S10: the realtime WebSocket requires a valid JWT passed as the `token` query parameter."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from starlette.websockets import WebSocketDisconnect

from app.security import ALGORITHM, SECRET_KEY
from app.ws import manager

PATHS = ["/ws", "/"]


def _token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("query", ["", "?token=", "?token=not-a-jwt"])
def test_ws_without_valid_token_is_rejected(client, path, query):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(path + query):
            pass
    assert exc.value.code == 1008
    assert manager.active_connections == []


@pytest.mark.parametrize("path", PATHS)
def test_ws_with_expired_token_is_rejected(client, monitor_headers, path):
    payload = jwt.decode(_token(monitor_headers), SECRET_KEY, algorithms=[ALGORITHM])
    payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=10)
    expired = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"{path}?token={expired}"):
            pass
    assert exc.value.code == 1008


@pytest.mark.parametrize("path", PATHS)
def test_ws_with_forged_signature_is_rejected(client, path):
    forged = jwt.encode({"sub": "admin", "role": "admin", "id": 1,
                         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                        "some-other-secret-key-0123456789abcdef", algorithm=ALGORITHM)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"{path}?token={forged}"):
            pass
    assert exc.value.code == 1008


@pytest.mark.parametrize("path", PATHS)
def test_ws_with_valid_token_still_receives_broadcasts(client, monitor_headers, path):
    with client.websocket_connect(f"{path}?token={_token(monitor_headers)}") as ws:
        assert len(manager.active_connections) == 1
        ws.portal.call(manager.broadcast_json, {"type": "ping"})
        assert ws.receive_json() == {"type": "ping"}
    assert manager.active_connections == []
