"""Siren microservice must reject unauthenticated callers and bound the duration."""
import importlib.util
import json
import pathlib
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

TOKEN = "unit-test-siren-token"
ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture
def siren_server(monkeypatch):
    monkeypatch.setenv("SARI_SIREN_TOKEN", TOKEN)
    spec = importlib.util.spec_from_file_location("sirena_service_ut", ROOT / "sirena_service.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []
    monkeypatch.setattr(mod, "_reproducir_alerta", lambda d: calls.append(("on", d)))
    monkeypatch.setattr(mod, "_desactivar_alerta", lambda: calls.append(("off", None)))
    server = HTTPServer(("127.0.0.1", 0), mod.SirenaHTTPHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", calls, mod
    server.shutdown()


def _post(url, body=None, token=None):
    req = urllib.request.Request(url, data=json.dumps(body or {}).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("X-SARI-Siren-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@pytest.mark.parametrize("path", ["/api/alarma/activar", "/api/alarma/desactivar"])
@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_rejects_missing_or_wrong_token(siren_server, path, token):
    base, calls, _ = siren_server
    status, _ = _post(base + path, {"duracion": 5}, token=token)
    assert status == 401
    assert calls == []


def test_valid_token_activates(siren_server):
    base, calls, _ = siren_server
    status, body = _post(base + "/api/alarma/activar", {"duracion": 5}, token=TOKEN)
    assert status == 200
    assert body["sirena_activa"] is True
    assert calls == [("on", 5)]


def test_valid_token_deactivates(siren_server):
    base, calls, _ = siren_server
    status, _ = _post(base + "/api/alarma/desactivar", token=TOKEN)
    assert status == 200
    assert calls == [("off", None)]


def test_duration_is_capped(siren_server):
    base, calls, mod = siren_server
    status, _ = _post(base + "/api/alarma/activar", {"duracion": 10**9}, token=TOKEN)
    assert status == 200
    assert calls == [("on", mod.MAX_DURATION_SECONDS)]


@pytest.mark.parametrize("bad", ["abc", -5, 0, None])
def test_invalid_duration_rejected(siren_server, bad):
    base, calls, _ = siren_server
    status, _ = _post(base + "/api/alarma/activar", {"duracion": bad}, token=TOKEN)
    assert status == 400
    assert calls == []


def test_health_stays_public(siren_server):
    base, _, _ = siren_server
    with urllib.request.urlopen(base + "/health", timeout=3) as r:
        assert r.status == 200


def test_service_refuses_to_start_without_token(monkeypatch):
    monkeypatch.delenv("SARI_SIREN_TOKEN", raising=False)
    spec = importlib.util.spec_from_file_location("sirena_service_nt", ROOT / "sirena_service.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(SystemExit):
        mod.iniciar_servicio()


def test_backend_sends_token_to_siren(client, admin_headers, siren):
    res = client.post("/api/hardware/manual_action", json={"action": "activar_sirena", "pin": "4321"}, headers=admin_headers)
    assert res.status_code == 200
    assert siren.calls, "backend did not call the siren service"
    assert siren.calls[0]["headers"]["X-SARI-Siren-Token"] == TOKEN
