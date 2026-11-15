"""A3 (S6) multi-process proof against a real PostgreSQL (and optionally a real MQTT broker).

Skipped unless ``SARI_TEST_POSTGRES_URL`` points at a THROWAWAY database (its name must end in
``_probe`` or ``_test``; nothing is dropped, rows are only added). With ``SARI_TEST_MQTT_PORT`` (and
``SARI_TEST_MQTT_HOST``, default 127.0.0.1) pointing at an anonymous broker it also proves that
only the worker consumes MQTT. Example (throwaway containers)::

    docker run --rm -d --name sari-probe-pg -e POSTGRES_USER=probe -e POSTGRES_PASSWORD=probe \\
        -e POSTGRES_DB=sari_probe -p 55432:5432 pgvector/pgvector:pg15
    SARI_TEST_POSTGRES_URL=postgresql://probe:probe@127.0.0.1:55432/sari_probe \\
        .venv/bin/pytest -q tests/unit/test_multiprocess_postgres.py

Proves: ``uvicorn --workers 2`` serves ``/health``; each API worker holds its own LISTEN connection;
a NOTIFY published by another process reaches every WebSocket client exactly once; and an MQTT alert
is ingested once, sounds the siren once and reaches the dashboard clients of the API workers.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest

PG_URL = os.environ.get("SARI_TEST_POSTGRES_URL", "")
MQTT_PORT = os.environ.get("SARI_TEST_MQTT_PORT", "")
MQTT_HOST = os.environ.get("SARI_TEST_MQTT_HOST", "127.0.0.1")
BACKEND = Path(__file__).resolve().parents[2] / "backend"
ADMIN_PASSWORD = "probe-admin-bootstrap"

pytestmark = pytest.mark.skipif(
    not PG_URL or not urlparse(PG_URL).path.rstrip("/").endswith(("_probe", "_test")),
    reason="needs SARI_TEST_POSTGRES_URL on a throwaway *_probe/*_test database",
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pg():
    import psycopg2

    conn = psycopg2.connect(PG_URL)
    conn.autocommit = True
    return conn


def _query(sql, args=()):
    conn = _pg()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else None
    finally:
        conn.close()


def _wait(predicate, timeout=30.0, step=0.25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return predicate()


class _Siren(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        _Siren.calls.append((self.path, self.rfile.read(length)))
        body = b'{"status": "ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    logs = tmp_path_factory.mktemp("mp")
    siren = HTTPServer(("127.0.0.1", 0), _Siren)
    threading.Thread(target=siren.serve_forever, daemon=True).start()
    port = _free_port()
    env = {
        **os.environ,
        "DATABASE_URL": PG_URL,
        "SARI_SECRET_KEY": "probe-secret-key-0123456789abcdef0123",
        "SARI_SECURITY_PIN": "4321",
        "MQTT_USER": "probe-brain",
        "MQTT_PASSWORD": "probe-broker-password",
        "MQTT_BROKER_HOST": MQTT_HOST,
        "MQTT_BROKER_PORT": MQTT_PORT or "1",
        "SARI_SIREN_TOKEN": "probe-siren-token",
        "SARI_ADMIN_PASSWORD": ADMIN_PASSWORD,
        "SARI_NODE_KEYS": "Jetson-PTZ_1:probe-node-key",
        "SIRENA_SERVICE_URL": f"http://127.0.0.1:{siren.server_port}",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_POLLING_ENABLED": "false",
        "PYTHONPATH": str(BACKEND),
    }
    procs = []
    api_env = {**env, "SARI_RUN_BACKGROUND": "false"}
    api_log = open(logs / "api.log", "w")
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
                            "--workers", "2"], cwd=BACKEND, env=api_env, stdout=api_log, stderr=subprocess.STDOUT)
    procs.append(api)
    worker = None
    if MQTT_PORT:
        worker_log = open(logs / "worker.log", "w")
        worker = subprocess.Popen([sys.executable, "-m", "app.worker"], cwd=BACKEND, env={**env, "SARI_RUN_BACKGROUND": "true"},
                                  stdout=worker_log, stderr=subprocess.STDOUT)
        procs.append(worker)
    try:
        yield {"port": port, "api": api, "worker": worker, "logs": logs, "siren": _Siren}
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        siren.shutdown()


def _get(stack, path, **kw):
    import requests

    return requests.get(f"http://127.0.0.1:{stack['port']}{path}", timeout=5, **kw)


def _listeners():
    return _query("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND query = 'LISTEN sari_ws'")[0][0]


def _token(stack):
    import requests

    res = requests.post(f"http://127.0.0.1:{stack['port']}/api/auth/login",
                        json={"username": "admin", "password": ADMIN_PASSWORD}, timeout=5)
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _clients(stack, count):
    from websockets.sync.client import connect

    token = _token(stack)
    return [connect(f"ws://127.0.0.1:{stack['port']}/ws?token={token}", open_timeout=5) for _ in range(count)]


def _recv_all(ws, timeout):
    out = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            out.append(json.loads(ws.recv(timeout=max(0.05, deadline - time.time()))))
        except TimeoutError:
            break
    return out


def test_two_api_workers_serve_health_and_each_listens(stack):
    assert _wait(lambda: _get_ok(stack), timeout=60), (stack["logs"] / "api.log").read_text()[-3000:]
    for _ in range(20):
        assert _get(stack, "/health").json() == {"status": "ok", "database": "up"}
    assert _wait(lambda: _listeners() >= 2, timeout=30)
    assert _listeners() == 2
    children = subprocess.run(["ps", "-o", "pid=", "--ppid", str(stack["api"].pid)], capture_output=True, text=True).stdout.split()
    assert len(children) >= 2


def _get_ok(stack):
    try:
        return _get(stack, "/health").status_code == 200
    except Exception:
        return False


def test_notify_from_another_process_reaches_every_client_once(stack):
    assert _wait(lambda: _get_ok(stack) and _listeners() == 2, timeout=60)
    clients = _clients(stack, 6)
    try:
        time.sleep(0.5)
        marker = uuid.uuid4().hex
        _query("SELECT pg_notify('sari_ws', %s)", (json.dumps({"event": "probe", "marker": marker}),))
        for ws in clients:
            got = [m for m in _recv_all(ws, 3.0) if m.get("marker") == marker]
            assert got == [{"event": "probe", "marker": marker}]
    finally:
        for ws in clients:
            ws.close()


@pytest.mark.skipif(not MQTT_PORT, reason="needs SARI_TEST_MQTT_PORT (anonymous throwaway broker)")
def test_mqtt_alert_is_ingested_once_by_the_worker_and_reaches_api_clients(stack):
    import paho.mqtt.client as mqtt

    assert _wait(lambda: _get_ok(stack) and _listeners() == 2, timeout=60)
    worker_log = stack["logs"] / "worker.log"
    assert _wait(lambda: "[MQTT] Subscribed to" in worker_log.read_text(), timeout=60), worker_log.read_text()[-3000:]
    api_log = (stack["logs"] / "api.log").read_text()
    assert "[MQTT]" not in api_log  # API workers never connect to the broker

    clients = _clients(stack, 4)
    try:
        time.sleep(0.5)
        before = len(stack["siren"].calls)
        marker = f"probe-{uuid.uuid4().hex}"
        pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"probe-{uuid.uuid4().hex[:8]}")
        pub.connect(MQTT_HOST, int(MQTT_PORT))
        pub.loop_start()
        pub.publish("sari/nodes/Jetson-PTZ_1/alerts", json.dumps({
            "event_type": "intrusion", "severity": "high", "message": marker, "confidence": 0.95,
            "camara_id": "Jetson-PTZ_1", "snapshot": "QUJD" * 4000,
        }), qos=1).wait_for_publish(5)
        pub.loop_stop()
        pub.disconnect()

        count_sql = "SELECT count(*) FROM chat_messages WHERE content LIKE %s"
        assert _wait(lambda: _query(count_sql, (f"%{marker}%",))[0][0] >= 1, timeout=20)
        received = [_recv_all(ws, 4.0) for ws in clients]
        time.sleep(2.0)
        assert _query(count_sql, (f"%{marker}%",))[0][0] == 1
        assert len(stack["siren"].calls) - before == 1
        for messages in received:
            siren_events = [m for m in messages if m.get("event") == "siren_activated"]
            assert {"event": "siren_activated"} in siren_events
            detailed = [m for m in siren_events if m.get("camara_id") == "Jetson-PTZ_1"]
            assert len(detailed) == 1
            assert detailed[0]["snapshot"] is None and detailed[0]["snapshot_omitted"] is True
    finally:
        for ws in clients:
            ws.close()
