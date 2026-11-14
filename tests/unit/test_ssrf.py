"""S11: stream URLs and node addresses are restricted to private node addresses (SSRF)."""
import pytest

from app import netpolicy
from app.routers import eyes as eyes_router
from app.routers.hardware import HardwareState

PIN = "4321"
EYE = {"node_id": "Jetson-S", "name": "SSRF eye", "ip": "192.168.55.9", "stream_url": "http://192.168.55.9:8080/mjpeg"}

ALLOWED_URLS = [
    "http://192.168.55.1:8080/mjpeg",
    "https://10.0.0.5/stream",
    "rtsp://user:pw@172.16.4.2:554/live",
    "http://172.31.255.254",
]
DENIED_URLS = [
    "http://127.0.0.1:7000/api/users",
    "http://localhost:5000/api/alarma/desactivar",
    "http://169.254.169.254/latest/meta-data/",
    "http://host.docker.internal:11434/api/ps",
    "http://8.8.8.8/",
    "http://172.32.0.1/",
    "http://0.0.0.0/",
    "http://[::1]/",
    "http://[fd00::1]/",
    "file:///etc/passwd",
    "gopher://192.168.1.1/",
    "ftp://192.168.1.1/",
    "http:///nohost",
    "http://example.com/stream",
    "http://192.168.1.1.nip.io/",
    "",
]


@pytest.mark.parametrize("url", ALLOWED_URLS)
def test_private_urls_are_allowed(url):
    assert netpolicy.is_allowed_stream_url(url)


@pytest.mark.parametrize("url", DENIED_URLS)
def test_dangerous_urls_are_denied(url):
    assert not netpolicy.is_allowed_stream_url(url)
    with pytest.raises(ValueError):
        netpolicy.validate_stream_url(url)


@pytest.mark.parametrize("ip", ["192.168.1.73", "10.1.2.3", "172.20.0.4"])
def test_private_node_ip_allowed(ip):
    assert netpolicy.validate_node_host(ip) == ip


@pytest.mark.parametrize("ip", ["127.0.0.1", "169.254.169.254", "8.8.8.8", "host.docker.internal", "evil.example.com", ""])
def test_bad_node_ip_denied(ip):
    with pytest.raises(ValueError):
        netpolicy.validate_node_host(ip)


def test_allowlisted_lan_hostname(monkeypatch):
    monkeypatch.setenv("SARI_ALLOWED_STREAM_HOSTS", "jetson-north.lan, Cam2.local")
    assert netpolicy.is_allowed_stream_url("http://jetson-north.lan:8080/mjpeg")
    assert netpolicy.is_allowed_stream_url("rtsp://cam2.local/live")
    assert netpolicy.validate_node_host("jetson-north.lan") == "jetson-north.lan"
    assert not netpolicy.is_allowed_stream_url("http://jetson-north.lan.evil.com/")


def test_allowlist_cannot_reopen_docker_host(monkeypatch):
    monkeypatch.setenv("SARI_ALLOWED_STREAM_HOSTS", "host.docker.internal,localhost")
    assert not netpolicy.is_allowed_stream_url("http://host.docker.internal:11434/")
    assert not netpolicy.is_allowed_stream_url("http://localhost:5000/")


# --- write time ---------------------------------------------------------------------------

def test_create_eye_with_private_stream_still_works(client, admin_headers):
    res = client.post("/api/eyes", json=EYE, headers=admin_headers)
    assert res.status_code == 201, res.text
    assert res.json()["stream_url"] == EYE["stream_url"]


@pytest.mark.parametrize("field,value", [("stream_url", "http://169.254.169.254/latest/"), ("ip", "127.0.0.1"), ("stream_url", "file:///etc/passwd")])
def test_create_eye_rejects_ssrf_targets(client, admin_headers, field, value):
    res = client.post("/api/eyes", json={**EYE, field: value}, headers=admin_headers)
    assert res.status_code == 422


@pytest.mark.parametrize("field,value", [("stream_url", "http://127.0.0.1:7000/"), ("ip", "8.8.8.8")])
def test_update_eye_rejects_ssrf_targets(client, admin_headers, field, value):
    client.post("/api/eyes", json=EYE, headers=admin_headers)
    res = client.put("/api/eyes/Jetson-S", json={field: value, "pin": PIN}, headers=admin_headers)
    assert res.status_code == 422
    eye = [e for e in client.get("/api/eyes", headers=admin_headers).json() if e["node_id"] == "Jetson-S"][0]
    assert eye[field] == EYE[field]


def test_update_eye_with_private_stream_still_works(client, admin_headers):
    client.post("/api/eyes", json=EYE, headers=admin_headers)
    res = client.put("/api/eyes/Jetson-S", json={"stream_url": "http://10.0.0.9:8080/mjpeg", "pin": PIN}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["stream_url"] == "http://10.0.0.9:8080/mjpeg"


# --- connection test ----------------------------------------------------------------------

class _FakeGet:
    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.exc:
            raise self.exc

        class _Resp:
            status_code = 200
            headers = {"Content-Type": "multipart/x-mixed-replace"}

        return _Resp()


@pytest.mark.parametrize("target", ["http://169.254.169.254/latest/meta-data/", "127.0.0.1:7000", "http://host.docker.internal:11434"])
def test_connection_test_refuses_ssrf_targets(client, admin_headers, monkeypatch, target):
    fake = _FakeGet()
    monkeypatch.setattr(eyes_router.requests, "get", fake)
    res = client.post("/api/eyes/test-connection", json={"target_url": target}, headers=admin_headers)
    assert res.status_code == 422
    assert fake.calls == []


def test_connection_test_private_target_still_works(client, admin_headers, monkeypatch):
    fake = _FakeGet()
    monkeypatch.setattr(eyes_router.requests, "get", fake)
    res = client.post("/api/eyes/test-connection", json={"target_url": "192.168.55.9:8080/mjpeg"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["reachable"] is True
    url, kwargs = fake.calls[0]
    assert url == "http://192.168.55.9:8080/mjpeg"
    assert kwargs.get("allow_redirects") is False


def test_connection_test_does_not_echo_upstream_errors(client, admin_headers, monkeypatch):
    secret = "HTTPConnectionPool(host='192.168.55.9') internal-detail-xyz"
    monkeypatch.setattr(eyes_router.requests, "get", _FakeGet(exc=ConnectionError(secret)))
    res = client.post("/api/eyes/test-connection", json={"target_url": "http://192.168.55.9:8080"}, headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["reachable"] is False
    assert "internal-detail-xyz" not in res.text
    assert body["error"]


# --- fetch time (Telegram snapshot) -------------------------------------------------------

def test_snapshot_fetch_skips_disallowed_urls(monkeypatch):
    from app.database import SessionLocal
    from app.telegram import bot

    fetched = []

    def _get(url, **kwargs):
        fetched.append((url, kwargs))
        raise ConnectionError("down")

    monkeypatch.setattr(bot.requests, "get", _get)
    HardwareState.nodes["Evil"] = {"node_id": "Evil", "ip": "169.254.169.254"}
    db = SessionLocal()
    try:
        assert bot.fetch_node_snapshot("Evil", "http://127.0.0.1:7000/mjpeg", db) is None
        assert fetched == []
        bot.fetch_node_snapshot("Evil", "http://192.168.55.9:8080/mjpeg", db)
    finally:
        db.close()
        HardwareState.nodes.pop("Evil", None)
    assert fetched and all(u.startswith("http://192.168.55.9") for u, _ in fetched)
    assert all(kw.get("allow_redirects") is False for _, kw in fetched)
