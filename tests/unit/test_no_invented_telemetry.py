"""T15 (S15): the dashboard never shows invented telemetry; unknown values are reported as None."""
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from app.routers import hardware
from app.routers.hardware import HardwareState

KEY = {"X-SARI-Node-Key": "unit-node-key"}
NODE_FIELDS = ("ram_used_gb", "ram_total_gb", "cpu_load_pct", "gpu_load_pct", "temp_c", "fps", "link_status")
BACKEND = Path(__file__).resolve().parents[2] / "backend"


@pytest.fixture(autouse=True)
def no_nodes():
    HardwareState.nodes.clear()
    yield
    HardwareState.nodes.clear()


def test_fresh_process_has_no_placeholder_node_or_unverified_boot_claims():
    code = (
        "import json; from app.routers.hardware import HardwareState as H; "
        "print(json.dumps({'nodes': H.nodes, 'logs': [log['message'] for log in H.logs]}))"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=dict(os.environ, PYTHONPATH=str(BACKEND)),
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    state = json.loads(out.stdout.strip().splitlines()[-1])
    assert state["nodes"] == {}
    assert not any("PostgreSQL" in m or "Audio microservice" in m for m in state["logs"])


def test_record_node_activity_stores_unknown_as_none():
    HardwareState.record_node_activity("n-new")
    node = HardwareState.nodes["n-new"]
    assert node["ip"] is None
    assert all(node[f] is None for f in NODE_FIELDS)


def test_record_node_activity_keeps_known_ip_and_refreshes_last_seen():
    HardwareState.record_node_activity("n-ip", ip="10.0.0.8")
    HardwareState.nodes["n-ip"]["last_seen"] = 1.0
    HardwareState.record_node_activity("n-ip", ip="10.0.0.8")
    assert HardwareState.nodes["n-ip"]["ip"] == "10.0.0.8"
    assert HardwareState.nodes["n-ip"]["last_seen"] > 1.0


def test_rest_telemetry_missing_fields_are_none(client):
    res = client.post("/api/hardware/telemetry/node", json={"node_id": "Jetson-PTZ_1"}, headers=KEY)
    assert res.status_code == 200, res.text
    node = HardwareState.nodes["Jetson-PTZ_1"]
    assert node["ip"] is None
    assert all(node[f] is None for f in NODE_FIELDS)


def test_rest_telemetry_reported_values_are_kept(client):
    full = {"node_id": "Jetson-PTZ_1", "ip": "10.0.0.5", "ram_used_gb": 2.5, "ram_total_gb": 8.0, "cpu_load_pct": 10.0,
            "gpu_load_pct": 20.0, "temp_c": 40.0, "fps": 15.0, "link_status": "Wi-Fi"}
    client.post("/api/hardware/telemetry/node", json=full, headers=KEY)
    node = HardwareState.nodes["Jetson-PTZ_1"]
    assert {k: node[k] for k in full} == full
    assert node["is_online"] is True


def test_mqtt_telemetry_missing_fields_are_none():
    from app.mqtt.handlers import handle_telemetry_message

    handle_telemetry_message("sari/nodes/n-mq/telemetry", json.dumps({"fps": 12.0}))
    node = HardwareState.nodes["n-mq"]
    assert node["fps"] == 12.0
    assert node["ip"] is None
    assert all(node[f] is None for f in NODE_FIELDS if f != "fps")


def test_mqtt_status_online_without_ip_stores_none():
    from app.mqtt.handlers import handle_status_message

    handle_status_message("sari/nodes/n-st/status", json.dumps({"status": "online"}))
    assert HardwareState.nodes["n-st"]["ip"] is None
    assert HardwareState.nodes["n-st"]["is_online"] is True


def _break_probes(monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", None)
    monkeypatch.setitem(sys.modules, "psutil", None)

    def _no_smi(*a, **kw):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(subprocess, "check_output", _no_smi)

    def _no_ollama(*a, **kw):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(hardware.requests, "get", _no_ollama)


def test_gpu_telemetry_unreadable_values_are_none(monkeypatch):
    _break_probes(monkeypatch)
    t = hardware.get_system_gpu_telemetry()
    for key in ("gpu_name", "gpu_load_pct", "vram_used_gb", "vram_total_gb", "vram_pct", "gpu_temp_c",
                "cpu_load_pct", "cpu_temp_c", "model_status"):
        assert t[key] is None, key
    assert t["has_gpu"] is False


def test_gpu_telemetry_reads_real_values(monkeypatch):
    """Previous behaviour: values read from NVML are reported as read."""
    _break_probes(monkeypatch)
    fake = types.SimpleNamespace(
        nvmlInit=lambda: None, nvmlShutdown=lambda: None, NVML_TEMPERATURE_GPU=0,
        nvmlDeviceGetHandleByIndex=lambda i: "h", nvmlDeviceGetName=lambda h: b"Fake GPU",
        nvmlDeviceGetUtilizationRates=lambda h: types.SimpleNamespace(gpu=37),
        nvmlDeviceGetMemoryInfo=lambda h: types.SimpleNamespace(used=2 * 1024 ** 3, total=8 * 1024 ** 3),
        nvmlDeviceGetTemperature=lambda h, s: 61,
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    t = hardware.get_system_gpu_telemetry()
    assert (t["gpu_name"], t["gpu_load_pct"], t["vram_used_gb"], t["vram_total_gb"], t["vram_pct"], t["gpu_temp_c"]) == (
        "Fake GPU", 37.0, 2.0, 8.0, 25.0, 61.0)
    assert t["has_gpu"] is True


def test_status_endpoint_serves_none_without_crashing(client, admin_headers, monkeypatch):
    _break_probes(monkeypatch)
    HardwareState.record_node_activity("n-status")
    res = client.get("/api/hardware/state", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["system_telemetry"]["gpu_temp_c"] is None
    assert [n for n in body["nodes"] if n["node_id"] == "n-status"][0]["fps"] is None
