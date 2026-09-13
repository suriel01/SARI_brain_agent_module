import os
import json
import time
import requests
import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "sari-mqtt")
BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", 1883))
BROKER_USER = os.environ.get("MQTT_USER", "sari_operator")
BROKER_PASS = os.environ.get("MQTT_PASSWORD", "sari_secure_password_2026")

def test_mqtt_to_http_fallback():
    # 1. Login to check backend
    login_res = requests.post(
        "http://127.0.0.1:7000/api/auth/login",
        json={"username": "admin", "password": "sari_password"},
        timeout=3.0
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Simulate MQTT primary
    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test_dual_mode")
    pub.username_pw_set(BROKER_USER, BROKER_PASS)
    pub.connect(BROKER_HOST, BROKER_PORT, 60)
    pub.loop_start()

    data_mqtt = {
        "node_id": "Jetson-DUAL_TEST",
        "name": "Jetson Orin (Dual Mode)",
        "ip": "192.168.1.73",
        "ram_used_gb": 3.9,
        "ram_total_gb": 7.44,
        "cpu_load_pct": 42.0,
        "gpu_load_pct": 65.0,
        "temp_c": 51.0,
        "fps": 30.0,
        "link_status": "Wi-Fi 5GHz (MQTT)"
    }

    inf = pub.publish("sari/nodes/Jetson-DUAL_TEST/telemetry", json.dumps(data_mqtt), qos=1)
    inf.wait_for_publish(timeout=2.0)
    time.sleep(0.5)

    state1 = requests.get("http://127.0.0.1:7000/api/hardware/state", headers=headers, timeout=3.0).json()
    n1 = next((n for n in state1["nodes"] if n["node_id"] == "Jetson-DUAL_TEST"), None)
    assert n1 is not None, "Node should exist after MQTT pub"
    assert n1["link_status"] == "Wi-Fi 5GHz (MQTT)"
    assert n1["is_online"] is True

    # 3. Simulate MQTT disconnect and fallback to HTTP REST
    pub.loop_stop()
    pub.disconnect()
    time.sleep(0.5)

    data_http = dict(data_mqtt)
    data_http["link_status"] = "Wi-Fi Fallback (HTTP)"
    data_http["temp_c"] = 53.5

    fallback_res = requests.post("http://127.0.0.1:7000/api/telemetry/node", json=data_http, timeout=2.0)
    assert fallback_res.status_code == 200, "HTTP fallback endpoint should succeed"

    state2 = requests.get("http://127.0.0.1:7000/api/hardware/state", headers=headers, timeout=3.0).json()
    n2 = next((n for n in state2["nodes"] if n["node_id"] == "Jetson-DUAL_TEST"), None)
    assert n2 is not None
    assert n2["link_status"] == "Wi-Fi Fallback (HTTP)"
    assert n2["temp_c"] == 53.5
    assert n2["is_online"] is True
    print("[+] test_mqtt_to_http_fallback passed successfully!")

if __name__ == "__main__":
    test_mqtt_to_http_fallback()
