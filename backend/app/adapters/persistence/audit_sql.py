"""AuditPort over the `physical_action_log` table."""
import logging
from typing import Optional

from ...database import SessionLocal
from ...domain.actions import canonical_action
from ...domain.actors import Actor
from ...models import models

logger = logging.getLogger("sari_hardware")


def record_physical_action(actor: Optional[Actor], tool_name: str, result: str, detail: str = "") -> None:
    """Persists one audit row (S8). Never raises: a broken audit DB must not block raising the alarm.

    Fail-open is deliberate for a siren: losing an audit row is preferable to a silent perimeter.
    The failure is logged at ERROR so it is visible.
    """
    try:
        db = SessionLocal()
    except Exception as exc:
        logger.error("Physical action audit unavailable (%s): %s by %s", exc, tool_name, actor.name if actor else "anonymous")
        return
    try:
        db.add(
            models.PhysicalActionLog(
                actor_name=(actor.name if actor else "anonymous")[:100],
                channel=(actor.channel if actor else "unknown")[:30],
                action=canonical_action(tool_name),
                result=result,
                detail=detail or None,
            )
        )
        db.commit()
    except Exception as exc:
        logger.error("Could not persist physical action audit row: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


class SqlAudit:
    def record(self, actor: Optional[Actor], tool_name: str, result: str, detail: str = "") -> None:
        record_physical_action(actor, tool_name, result, detail)
