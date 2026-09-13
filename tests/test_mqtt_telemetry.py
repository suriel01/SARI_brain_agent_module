import json
import time
import pytest
import paho.mqtt.client as mqtt

import os
BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "sari-mqtt")
BROKER_PORT = 1883
BROKER_USER = "sari_operator"
BROKER_PASS = "sari_secure_password_2026"

def test_mqtt_telemetry_publish_and_receive():
    received = []

    def on_connect(client, userdata, flags, rc, properties=None):
        assert rc == 0, f"Failed to connect, rc={rc}"
        client.subscribe("sari/nodes/+/telemetry")

    def on_message(client, userdata, msg):
        payload = json.loads(msg.payload.decode("utf-8"))
        received.append((msg.topic, payload))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test_subscriber")
    client.username_pw_set(BROKER_USER, BROKER_PASS)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()

    time.sleep(0.5)

    # Publisher client
    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test_jetson_pub")
    pub.username_pw_set(BROKER_USER, BROKER_PASS)
    pub.connect(BROKER_HOST, BROKER_PORT, 60)

    test_payload = {
        "node_id": "Jetson-PTZ_1",
        "name": "Jetson Orin Nano (PTZ 1)",
        "ip": "192.168.1.73",
        "ram_used_gb": 3.82,
        "ram_total_gb": 7.44,
        "cpu_load_pct": 34.0,
        "gpu_load_pct": 62.0,
        "temp_c": 53.0,
        "fps": 30.0,
        "link_status": "Wi-Fi 5GHz (Stable)"
    }

    pub.publish("sari/nodes/Jetson-PTZ_1/telemetry", json.dumps(test_payload), qos=0)
    pub.disconnect()

    # Wait for receipt
    start = time.time()
    while time.time() - start < 3.0:
        if received:
            break
        time.sleep(0.1)

    client.loop_stop()
    client.disconnect()

    assert len(received) >= 1, "Should have received telemetry message via MQTT"
    topic, data = received[0]
    assert topic == "sari/nodes/Jetson-PTZ_1/telemetry"
    assert data["node_id"] == "Jetson-PTZ_1"
    assert data["ram_used_gb"] == 3.82
    assert data["temp_c"] == 53.0
    print("[+] test_mqtt_telemetry_publish_and_receive passed successfully!")

if __name__ == "__main__":
    test_mqtt_telemetry_publish_and_receive()


def test_backend_hardware_state_updates_from_mqtt():
    import urllib.request
    
    # 1. Login to get access token
    login_req = urllib.request.Request(
        "http://127.0.0.1:7000/api/auth/login",
        data=json.dumps({"username": "admin", "password": "sari_password"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req, timeout=3.0) as login_resp:
        login_data = json.loads(login_resp.read().decode())
    token = login_data["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test_jetson_hardware_sync")
    pub.username_pw_set(BROKER_USER, BROKER_PASS)
    pub.connect(BROKER_HOST, BROKER_PORT, 60)
    pub.loop_start()

    test_payload = {
        "node_id": "Jetson-PTZ_MQTT_TEST",
        "name": "Jetson Orin Nano (MQTT Test)",
        "ip": "192.168.1.150",
        "ram_used_gb": 4.10,
        "ram_total_gb": 7.44,
        "cpu_load_pct": 45.0,
        "gpu_load_pct": 78.0,
        "temp_c": 56.5,
        "fps": 28.5,
        "link_status": "Wi-Fi 5GHz (Stable)"
    }

    inf = pub.publish("sari/nodes/Jetson-PTZ_MQTT_TEST/telemetry", json.dumps(test_payload), qos=1)
    inf.wait_for_publish(timeout=2.0)
    time.sleep(0.5)

    # Check backend hardware state via internal HTTP API
    req = urllib.request.Request("http://127.0.0.1:7000/api/hardware/state", headers=auth_headers)
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        data = json.loads(resp.read().decode())
    
    assert "nodes" in data, "Hardware state should contain nodes list"
    node = next((n for n in data["nodes"] if n["node_id"] == "Jetson-PTZ_MQTT_TEST"), None)
    assert node is not None, f"Node Jetson-PTZ_MQTT_TEST should be present in hardware state: {data['nodes']}"
    assert node["is_online"] is True, f"Node is_online should be True, got {node}"
    assert node["temp_c"] == 56.5
    assert node["cpu_load_pct"] == 45.0

    # Now test LWT / offline status
    inf2 = pub.publish("sari/nodes/Jetson-PTZ_MQTT_TEST/status", json.dumps({"status": "offline"}), qos=1)
    inf2.wait_for_publish(timeout=2.0)
    time.sleep(0.5)

    with urllib.request.urlopen(req, timeout=3.0) as resp:
        data_after = json.loads(resp.read().decode())
    node_after = next((n for n in data_after["nodes"] if n["node_id"] == "Jetson-PTZ_MQTT_TEST"), None)
    assert node_after is None or node_after["is_online"] is False, f"Expected offline after status publication, got {node_after}"

    pub.loop_stop()
    pub.disconnect()
    print("[+] test_backend_hardware_state_updates_from_mqtt passed successfully!")
