"""S10: Eyes mutating endpoints require can_control_hardware; reads stay open to any logged-in user."""
import pytest

PIN = "4321"
EYE = {"node_id": "Jetson-T", "name": "Test eye", "ip": "192.168.55.9", "stream_url": "http://192.168.55.9:8080/mjpeg"}

MUTATIONS = [
    ("post", "/api/eyes", EYE),
    ("post", "/api/eyes/", EYE),
    ("put", "/api/eyes/Jetson-T", {"name": "renamed", "pin": PIN}),
    ("delete", "/api/eyes/Jetson-T", None),
    ("post", "/api/eyes/Jetson-T/tracking", {"enabled": False}),
    ("post", "/api/eyes/Jetson-T/ptz", {"action": "left"}),
    ("post", "/api/eyes/test-connection", {"target_url": "http://192.168.55.9:8080"}),
]


def _call(client, method, path, body, headers):
    kwargs = {"headers": headers}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(path, **kwargs)


@pytest.fixture
def operator_headers(make_user):
    return make_user("eye_op", role="monitor", can_control_hardware=True)


@pytest.fixture
def seeded_eye(client, admin_headers):
    res = client.post("/api/eyes", json=EYE, headers=admin_headers)
    assert res.status_code == 201, res.text


@pytest.mark.parametrize("method,path,body", MUTATIONS)
def test_monitor_without_hardware_perm_cannot_mutate_eyes(client, monitor_headers, seeded_eye, method, path, body):
    res = _call(client, method, path, body, monitor_headers)
    assert res.status_code == 403, res.text


@pytest.mark.parametrize("method,path,body", MUTATIONS)
def test_anonymous_cannot_mutate_eyes(client, seeded_eye, method, path, body):
    res = _call(client, method, path, body, {})
    assert res.status_code in (401, 403)


def test_monitor_mutation_leaves_eye_unchanged(client, monitor_headers, admin_headers, seeded_eye):
    client.put("/api/eyes/Jetson-T", json={"name": "hacked", "pin": PIN}, headers=monitor_headers)
    client.delete("/api/eyes/Jetson-T", headers=monitor_headers)
    eyes = client.get("/api/eyes", headers=admin_headers).json()
    assert [e["name"] for e in eyes if e["node_id"] == "Jetson-T"] == ["Test eye"]


def test_operator_with_hardware_perm_can_manage_eyes(client, operator_headers):
    assert client.post("/api/eyes", json=EYE, headers=operator_headers).status_code == 201
    res = client.put("/api/eyes/Jetson-T", json={"name": "renamed", "pin": PIN}, headers=operator_headers)
    assert res.status_code == 200 and res.json()["name"] == "renamed"
    assert client.post("/api/eyes/Jetson-T/tracking", json={"enabled": False}, headers=operator_headers).status_code == 200
    assert client.post("/api/eyes/Jetson-T/ptz", json={"action": "left"}, headers=operator_headers).status_code == 200
    assert client.delete("/api/eyes/Jetson-T", headers=operator_headers).status_code == 200


def test_operator_update_still_requires_pin(client, operator_headers, seeded_eye):
    res = client.put("/api/eyes/Jetson-T", json={"name": "renamed", "pin": ""}, headers=operator_headers)
    assert res.status_code == 401


def test_any_logged_in_user_can_still_read_eyes(client, monitor_headers, seeded_eye):
    res = client.get("/api/eyes", headers=monitor_headers)
    assert res.status_code == 200
    assert [e["node_id"] for e in res.json()] == ["Jetson-T"]
    assert client.get("/api/eyes/recordings", headers=monitor_headers).status_code == 200
