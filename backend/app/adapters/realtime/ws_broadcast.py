"""BroadcastPort over the dashboard WebSocket. The one place that publishes a realtime event.

On PostgreSQL every event is published with ``NOTIFY sari_ws`` and each API worker runs one
`NotifyListener` that fans it out to its own WebSocket clients, so a client connected to any API
worker receives events raised by any process (other API workers, the background worker). On other
databases (SQLite in unit tests and single-process development) the event is delivered in-process.
"""
import asyncio
import json
import logging
import select
import threading
from typing import Awaitable, Callable, Optional

from ...ws import manager

logger = logging.getLogger("sari_realtime")

CHANNEL = "sari_ws"
# PostgreSQL rejects NOTIFY payloads of 8000 bytes or more; keep a margin.
NOTIFY_MAX_BYTES = 7900


def _engine():
    from ...database import engine

    return engine


def uses_postgres() -> bool:
    return _engine().dialect.name == "postgresql"


def notify_payload(payload: dict) -> str:
    """JSON for NOTIFY, at most ``NOTIFY_MAX_BYTES``. An oversized snapshot is dropped (marked with
    ``snapshot_omitted``; clients load it from the thread); if that is not enough only the event name is kept."""
    text = json.dumps(payload)  # ASCII only: length in characters == length in bytes
    if len(text) <= NOTIFY_MAX_BYTES:
        return text
    if "snapshot" in payload:
        text = json.dumps({**payload, "snapshot": None, "snapshot_omitted": True})
        if len(text) <= NOTIFY_MAX_BYTES:
            return text
    return json.dumps({"event": payload.get("event"), "truncated": True})


def notify(payload: dict, warn: bool = False) -> bool:
    """Publishes one event to every API worker. Best effort: never raises."""
    try:
        with _engine().connect() as conn:
            conn.exec_driver_sql("SELECT pg_notify(%(channel)s, %(payload)s)",
                                 {"channel": CHANNEL, "payload": notify_payload(payload)})
            conn.commit()
        return True
    except Exception as ex:
        (logger.warning if warn else logger.debug)("Could not publish realtime event: %s", ex)
        return False


def _broadcast_in_process(payload: dict, background_tasks=None, *, warn: bool = False) -> None:
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


def broadcast(payload: dict, background_tasks=None, *, warn: bool = False) -> None:
    """Best-effort WebSocket notification.

    With FastAPI `background_tasks` the publish runs after the response. On PostgreSQL the event
    goes through NOTIFY from any thread or process. Otherwise it is scheduled on the running event
    loop; outside one (worker threads, MQTT callbacks) it is dropped, logged only when `warn` is set.
    """
    if uses_postgres():
        if background_tasks is not None:
            background_tasks.add_task(notify, payload, warn)
        else:
            notify(payload, warn)
        return
    _broadcast_in_process(payload, background_tasks, warn=warn)


class WsBroadcast:
    def publish(self, payload: dict, background_tasks=None, *, warn: bool = False) -> None:
        broadcast(payload, background_tasks, warn=warn)


def dispatch_notification(raw: str, loop: asyncio.AbstractEventLoop,
                          deliver: Callable[[dict], Awaitable[None]]) -> bool:
    """Hands one NOTIFY payload to this worker's WebSocket clients on its event loop."""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Ignored malformed realtime notification")
        return False
    if not isinstance(payload, dict):
        return False
    asyncio.run_coroutine_threadsafe(deliver(payload), loop)
    return True


class NotifyListener:
    """One per API worker: ``LISTEN sari_ws`` on a dedicated connection, reconnecting on failure."""

    def __init__(self, loop: asyncio.AbstractEventLoop, deliver: Optional[Callable[[dict], Awaitable[None]]] = None,
                 retry_seconds: float = 2.0):
        self._loop = loop
        self._deliver = deliver or manager.broadcast_json
        self._retry_seconds = retry_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="sari-ws-listener")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _listen_once(self) -> None:
        raw = _engine().raw_connection()
        conn = raw.driver_connection
        raw.detach()  # dedicated connection, never returned to the pool
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"LISTEN {CHANNEL}")
            logger.info("Realtime listener subscribed to %s", CHANNEL)
            while not self._stop.is_set():
                if select.select([conn], [], [], 1.0) == ([], [], []):
                    continue
                conn.poll()
                while conn.notifies:
                    dispatch_notification(conn.notifies.pop(0).payload, self._loop, self._deliver)
        finally:
            conn.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._listen_once()
            except Exception as ex:
                logger.warning("Realtime listener lost its connection (%s); retrying in %ss", ex, self._retry_seconds)
                self._stop.wait(self._retry_seconds)


_listener: Optional[NotifyListener] = None


def start_listener(loop: asyncio.AbstractEventLoop) -> Optional[NotifyListener]:
    """Starts this worker's listener on PostgreSQL; on other databases delivery is in-process."""
    global _listener
    if not uses_postgres() or _listener is not None:
        return _listener
    _listener = NotifyListener(loop)
    _listener.start()
    return _listener


def stop_listener() -> None:
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None
