"""BroadcastPort over the dashboard WebSocket manager. The one place that schedules a broadcast."""
import asyncio
import logging

from ...ws import manager

logger = logging.getLogger("sari_realtime")


def broadcast(payload: dict, background_tasks=None, *, warn: bool = False) -> None:
    """Best-effort WebSocket notification.

    With FastAPI `background_tasks` the send runs after the response. Otherwise it is scheduled on
    the running event loop; outside one (worker threads, MQTT callbacks) it is dropped, logged only
    when `warn` is set.
    """
    if background_tasks is not None:
        background_tasks.add_task(manager.broadcast_json, payload)
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast_json(payload))
    except Exception as ex:
        if warn:
            logger.warning("Could not broadcast via ws: %s", ex)


class WsBroadcast:
    def publish(self, payload: dict, background_tasks=None, *, warn: bool = False) -> None:
        broadcast(payload, background_tasks, warn=warn)
