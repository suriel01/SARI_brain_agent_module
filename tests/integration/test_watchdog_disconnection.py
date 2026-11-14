import os
import time
import pytest
from unittest.mock import patch, MagicMock

def test_watchdog_disconnection_alert_and_debouncing():
    os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABC-DEF"
    os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = "987654321"

    from app.telegram.watchdog import trigger_node_disconnection_alert, reset_node_connection_state, _disconnected_nodes_notified
    from app.routers.hardware import HardwareState

    # Ensure node is known in HardwareState
    HardwareState.nodes["Jetson-PTZ_WATCHDOG"] = {
        "node_id": "Jetson-PTZ_WATCHDOG",
        "name": "Jetson Watchdog Test",
        "ip": "192.168.1.199",
        "is_online": True,
        "last_seen": time.time()
    }

    # Clear state
    reset_node_connection_state("Jetson-PTZ_WATCHDOG")

    with patch("app.telegram.service.send_telegram_alert_photo") as mock_photo,          patch("app.telegram.service.send_telegram_message") as mock_msg:
        
        mock_photo.return_value = True
        mock_msg.return_value = True

        # 1. First disconnection: should trigger alert
        alert_sent = trigger_node_disconnection_alert("Jetson-PTZ_WATCHDOG", reason="corte_lwt")
        assert alert_sent is True, "First disconnection must trigger an alert"
        assert mock_msg.called, "Disconnection alert must send text message"
        assert not mock_photo.called, "Disconnection alert must NOT send photo/capture"

        # 2. Second immediate call (debouncing): should NOT trigger duplicate alert
        mock_photo.reset_mock()
        mock_msg.reset_mock()
        duplicate_sent = trigger_node_disconnection_alert("Jetson-PTZ_WATCHDOG", reason="corte_lwt")
        assert duplicate_sent is False, "Duplicate call must be suppressed by debouncing"
        assert not mock_photo.called and not mock_msg.called

        # 3. Node reconnects: reset connection state
        reset_node_connection_state("Jetson-PTZ_WATCHDOG")

        # 4. Next disconnection should trigger again
        re_alert = trigger_node_disconnection_alert("Jetson-PTZ_WATCHDOG", reason="timeout")
        assert re_alert is True, "Subsequent disconnection after reconnect must trigger alert"

    print("[+] test_watchdog_disconnection_alert_and_debouncing passed successfully!")

if __name__ == "__main__":
    test_watchdog_disconnection_alert_and_debouncing()
