"""Regressions found by the independent verifier."""
import pytest

from app.netpolicy import validate_stream_url
from app.routers.hardware import HardwareState


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:9\\@10.0.0.5/",
        "http://169.254.169.254\\@10.0.0.5/latest",
        "http://sari-sirena:5000\\@10.0.0.5/",
        "http://10.0.0.5%2F@127.0.0.1/",
        "http://10.0.0.5\t/mjpeg",
        "http://10.0.0.5/\nHost: x",
    ],
)
def test_parser_confusion_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_stream_url(url)


def test_camera_credentials_in_url_still_allowed():
    assert validate_stream_url("rtsp://admin:pw@192.168.1.20:554/Streaming/Channels/101")
    assert validate_stream_url("http://user@10.0.0.5/mjpeg")


def test_plain_private_url_still_allowed():
    assert validate_stream_url("http://10.0.0.5:8080/mjpeg") == "http://10.0.0.5:8080/mjpeg"
    assert validate_stream_url("rtsp://192.168.1.20:554/stream1") == "rtsp://192.168.1.20:554/stream1"


def test_backslash_url_rejected_by_api(client, admin_headers):
    res = client.post(
        "/api/eyes/test-connection",
        json={"stream_url": "http://127.0.0.1:9\\@10.0.0.5/", "pin": "4321"},
        headers=admin_headers,
    )
    assert res.status_code == 422


@pytest.fixture
def _clean_nodes():
    HardwareState.nodes.clear()
    yield
    HardwareState.nodes.clear()


def test_mqtt_telemetry_cannot_spoof_another_node(_clean_nodes):
    from app.mqtt.handlers import route_message

    route_message("sari/nodes/Jetson-PTZ_1/telemetry", '{"node_id": "Jetson-PTZ_2", "fps": 99}')
    assert "Jetson-PTZ_2" not in HardwareState.nodes


def test_mqtt_status_cannot_spoof_another_node(_clean_nodes):
    from app.mqtt.handlers import route_message

    route_message("sari/nodes/Jetson-PTZ_1/status", '{"node_id": "Jetson-PTZ_2", "status": "offline"}')
    assert "Jetson-PTZ_2" not in HardwareState.nodes


def test_mqtt_telemetry_for_own_node_still_recorded(_clean_nodes):
    from app.mqtt.handlers import route_message

    route_message("sari/nodes/Jetson-PTZ_1/telemetry", '{"node_id": "Jetson-PTZ_1", "fps": 12}')
    assert HardwareState.nodes["Jetson-PTZ_1"]["fps"] == 12
