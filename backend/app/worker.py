"""SARI background worker: ``python -m app.worker``.

The only process that consumes MQTT, polls Telegram, runs the anti-tamper watchdog and the
maintenance scheduler (siren auto-off, ghost-node pruning, log purge). API workers
(``uvicorn app.main:app --workers N``) start none of these unless ``SARI_RUN_BACKGROUND=true``
(single-process development only), so alerts are ingested once and Telegram is polled once.
"""
import logging
import signal
import threading
import time
from typing import Optional

from .application.maintenance import SIREN_AUTO_OFF_SECONDS, run_maintenance
from .config import get_settings

logger = logging.getLogger("sari_worker")

SCHEDULER_INTERVAL_SECONDS = 2.0

_scheduler_stop: Optional[threading.Event] = None
_scheduler_thread: Optional[threading.Thread] = None


def registered_node_ids() -> set:
    from .database import SessionLocal
    from .models import models

    db = SessionLocal()
    try:
        return {row.node_id for row in db.query(models.EyeNode.node_id).filter(models.EyeNode.is_active.is_(True))}
    finally:
        db.close()


def maintenance_tick(now: Optional[float] = None):
    """One scheduler pass over the shared state."""
    from .adapters.composition import state

    now = time.time() if now is None else now
    result = run_maintenance(state, registered_node_ids(), now)
    try:
        from .adapters.composition import alarm

        siren = alarm.tick(now)
        if siren is not None:
            logger.warning("[WORKER] Entry delay expired: siren %s", siren.get("status"))
    except Exception:
        logger.exception("[WORKER] Alarm timer pass failed")
    if result.siren_expired:
        logger.info("[WORKER] Siren auto-off after %ss without alerts", SIREN_AUTO_OFF_SECONDS)
    if result.pruned_nodes:
        logger.info("[WORKER] Pruned stale unregistered nodes: %s", ", ".join(result.pruned_nodes))
    return result


def run_scheduler(stop: threading.Event, interval: float = SCHEDULER_INTERVAL_SECONDS) -> None:
    """Runs ``maintenance_tick`` every ``interval`` seconds until ``stop`` is set. A failing pass is logged, never fatal."""
    while not stop.is_set():
        try:
            maintenance_tick()
        except Exception:
            logger.exception("[WORKER] Maintenance pass failed")
        stop.wait(interval)


def log_boot() -> None:
    """Boot entries for the operational log; written only after the schema step and seed succeeded."""
    from .adapters.composition import state

    state.add_log("🧠 Brain Module online & listening for YOLO vision node alerts.", level="INFO", camera_module="SYS_CORE")
    state.add_log("🔐 Database reachable; schema at the latest migration.", level="INFO", camera_module="SYS_CORE")


def start_background_services() -> None:
    """Starts MQTT, Telegram polling, the watchdog and the maintenance scheduler (each failure is isolated)."""
    global _scheduler_stop, _scheduler_thread
    try:
        from .mqtt.client import start_mqtt_client
        start_mqtt_client()
    except Exception as e:
        logger.error("[MQTT] Error starting background client: %s", e)

    try:
        from .telegram.bot import start_telegram_bot
        from .telegram.watchdog import start_watchdog
        start_telegram_bot()
        start_watchdog()
    except Exception as e:
        logger.error("[Telegram] Error starting bot/watchdog: %s", e)

    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _scheduler_stop = threading.Event()
        _scheduler_thread = threading.Thread(target=run_scheduler, args=(_scheduler_stop,), daemon=True,
                                             name="sari-scheduler")
        _scheduler_thread.start()


def stop_background_services() -> None:
    global _scheduler_thread
    if _scheduler_stop is not None:
        _scheduler_stop.set()
    _scheduler_thread = None
    try:
        from .mqtt.client import stop_mqtt_client
        stop_mqtt_client()
    except Exception as e:
        logger.error("[MQTT] Error stopping background client: %s", e)
    try:
        from .telegram.bot import stop_telegram_bot
        from .telegram.watchdog import stop_watchdog
        stop_telegram_bot()
        stop_watchdog()
    except Exception as e:
        logger.error("[Telegram] Error stopping bot/watchdog: %s", e)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    get_settings()  # fail closed, as the API does
    from .main import bootstrap_database

    bootstrap_database()
    log_boot()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    start_background_services()
    logger.info("[WORKER] SARI worker running (MQTT, Telegram, watchdog, scheduler every %ss)", SCHEDULER_INTERVAL_SECONDS)
    try:
        while not stop.wait(1.0):
            pass
    finally:
        stop_background_services()
        logger.info("[WORKER] SARI worker stopped")


if __name__ == "__main__":
    main()
