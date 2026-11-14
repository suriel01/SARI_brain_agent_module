"""Alarm modes over HTTP: read the status and timeline, arm and disarm with the PIN."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..adapters.composition import alarm
from ..domain.actors import Actor
from ..security import require_pin
from .deps import get_current_user

router = APIRouter()

HTTP_STATUS = {"denied": 403, "invalid_mode": 400, "invalid_transition": 409, "failed_to_arm": 409}


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


@router.post("/arm")
def arm_alarm(req: ArmRequest, current_user: dict = Depends(get_current_user)):
    require_pin(req.pin, key=f"user:{current_user.get('id')}")
    return _respond(alarm.arm(Actor.from_user(current_user, "rest"), req.mode, force=req.force))


@router.post("/disarm")
def disarm_alarm(req: DisarmRequest, current_user: dict = Depends(get_current_user)):
    require_pin(req.pin, key=f"user:{current_user.get('id')}")
    return _respond(alarm.disarm(Actor.from_user(current_user, "rest")))
