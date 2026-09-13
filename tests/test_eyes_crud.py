import pytest
import requests
import json

BASE_URL = "http://127.0.0.1:7000"

def get_auth_token():
    res = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "sari_password"},
        timeout=3.0
    )
    assert res.status_code == 200, "Login failed"
    return res.json()["access_token"]

def test_eyes_crud_and_connection():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET /api/eyes - Should list nodes (including default Jetson-PTZ_1)
    res = requests.get(f"{BASE_URL}/api/eyes", headers=headers, timeout=3.0)
    assert res.status_code == 200, f"Expected 200 from GET /api/eyes, got {res.status_code}"
    eyes = res.json()
    assert isinstance(eyes, list), "Response should be a list"
    assert any(e["node_id"] == "Jetson-PTZ_1" for e in eyes), "Default Jetson-PTZ_1 should exist"

    # 2. POST /api/eyes - Create a new Eye node
    new_node = {
        "node_id": "Jetson-PTZ_TEST_EYE",
        "name": "Cámara Perimetral Test",
        "ip": "192.168.1.188",
        "stream_url": "http://192.168.1.188:8080/mjpeg",
        "yolo_threshold": 0.80
    }
    create_res = requests.post(f"{BASE_URL}/api/eyes", json=new_node, headers=headers, timeout=3.0)
    assert create_res.status_code in [200, 201], f"Create failed: {create_res.text}"
    created_data = create_res.json()
    assert created_data["node_id"] == "Jetson-PTZ_TEST_EYE"

    # 3. GET /api/eyes - Verify new node is present
    res2 = requests.get(f"{BASE_URL}/api/eyes", headers=headers, timeout=3.0)
    eyes2 = res2.json()
    assert any(e["node_id"] == "Jetson-PTZ_TEST_EYE" for e in eyes2)

    # 4. PUT /api/eyes/Jetson-PTZ_TEST_EYE - Update configuration
    update_data = {
        "name": "Cámara Perimetral Test Actualizada",
        "yolo_threshold": 0.85
    }
    update_res = requests.put(f"{BASE_URL}/api/eyes/Jetson-PTZ_TEST_EYE", json=update_data, headers=headers, timeout=3.0)
    assert update_res.status_code == 200, f"Update failed: {update_res.text}"
    assert update_res.json()["name"] == "Cámara Perimetral Test Actualizada"

    # 5. POST /api/eyes/test-connection - Test reachability
    test_conn_res = requests.post(
        f"{BASE_URL}/api/eyes/test-connection",
        json={"target_url": "http://127.0.0.1:7000/health"},
        headers=headers,
        timeout=3.0
    )
    assert test_conn_res.status_code == 200
    assert test_conn_res.json().get("reachable") is True

    # 6. DELETE /api/eyes/Jetson-PTZ_TEST_EYE - Clean up
    del_res = requests.delete(f"{BASE_URL}/api/eyes/Jetson-PTZ_TEST_EYE", headers=headers, timeout=3.0)
    assert del_res.status_code == 200, f"Delete failed: {del_res.text}"

    # Verify deleted
    res3 = requests.get(f"{BASE_URL}/api/eyes", headers=headers, timeout=3.0)
    assert not any(e["node_id"] == "Jetson-PTZ_TEST_EYE" for e in res3.json())
    print("[+] test_eyes_crud_and_connection passed successfully!")

if __name__ == "__main__":
    test_eyes_crud_and_connection()
