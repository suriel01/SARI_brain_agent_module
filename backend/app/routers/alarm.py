"""Alarm modes over HTTP: read the status and timeline, arm and disarm with the PIN."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..adapters.composition import alarm
from ..application.alarm import DISARM_TOOL, arm_tool
from ..domain.actors import Actor
from ..domain.alarm import ArmMode, InvalidTransition
from ..security import require_pin
from .deps import get_current_user

router = APIRouter()

HTTP_STATUS = {"denied": 403, "invalid_mode": 400, "invalid_transition": 409, "failed_to_arm": 409, "failed": 503}


class ArmRequest(BaseModel):
    mode: str
    pin: Optional[str] = None
    force: bool = False


class DisarmRequest(BaseModel):
    pin: Optional[str] = None


def _respond(result: dict) -> dict:
    status = result.get("status")
    if status == "success":
        return result
    raise HTTPException(status_code=HTTP_STATUS.get(status, 500), detail=result)


@router.get("")
def get_alarm(current_user: dict = Depends(get_current_user)):
    return alarm.view()


@router.get("/timeline")
def get_timeline(limit: int = 50, current_user: dict = Depends(get_current_user)):
    return alarm.timeline(limit)


def _authorize(current_user: dict, tool: str, pin: Optional[str]) -> Actor:
    """Permission first (audited), then the PIN (wrong guesses audited and rate limited)."""
    actor = Actor.from_user(current_user, "rest")
    denied = alarm.check_permission(actor, tool)
    if denied:
        raise HTTPException(status_code=403, detail=denied)
    try:
        require_pin(pin, key=f"user:{current_user.get('id')}")
    except HTTPException as exc:
        alarm.reject_pin(actor, tool, f"invalid PIN (HTTP {exc.status_code})")
        raise
    return actor


@router.post("/arm")
def arm_alarm(req: ArmRequest, current_user: dict = Depends(get_current_user)):
    try:
        mode = ArmMode.parse(req.mode)
    except InvalidTransition as exc:
        raise HTTPException(status_code=400, detail={"status": "invalid_mode", "message": str(exc)})
    actor = _authorize(current_user, arm_tool(mode), req.pin)
    return _respond(alarm.arm(actor, mode.value, force=req.force))


@router.post("/disarm")
def disarm_alarm(req: DisarmRequest, current_user: dict = Depends(get_current_user)):
    actor = _authorize(current_user, DISARM_TOOL, req.pin)
    return _respond(alarm.disarm(actor))
