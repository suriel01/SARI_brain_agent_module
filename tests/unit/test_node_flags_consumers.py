"""A3 (S5/S6): the watchdog debounce and the operator tracking choice live in the StateRepository."""
from app.adapters.composition import state


def test_watchdog_debounce_is_stored_in_the_repository(monkeypatch):
    from app.telegram import watchdog

    monkeypatch.setattr(watchdog.telegram_service, "send_telegram_message", lambda text, **k: True)
    assert watchdog.trigger_node_disconnection_alert("F-1") is True
    # Another process (same database) sees the debounce.
    assert state.mark_disconnect_notified("F-1") is False
    watchdog.reset_node_connection_state("F-1")
    assert state.mark_disconnect_notified("F-1") is True


def test_watchdog_alerts_even_when_the_store_is_down(monkeypatch):
    from app.telegram import watchdog

    def down(*_a, **_k):
        raise RuntimeError("database unavailable")

    sent = []
    monkeypatch.setattr(watchdog.telegram_service, "send_telegram_message", lambda text, **k: sent.append(text) or True)
    for name in ("mark_disconnect_notified", "get_node", "add_log", "clear_disconnect_notified"):
        monkeypatch.setattr(watchdog.state, name, down)
    assert watchdog.trigger_node_disconnection_alert("F-2") is True
    watchdog.reset_node_connection_state("F-2")  # logged, never raised
    assert len(sent) == 1 and "`F-2`" in sent[0]


def test_tracking_choice_is_stored_in_the_repository(client, admin_headers):
    assert client.post("/api/eyes/F-3/tracking", json={"enabled": False}, headers=admin_headers).status_code == 200
    assert state.tracking_overrides() == {"F-3": False}
