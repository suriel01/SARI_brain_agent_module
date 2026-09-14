from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import requests
import time
import urllib.parse
from ..database import get_db
from ..models import models
from ..schemas import schemas
from .deps import get_current_user
from .hardware import HardwareState

router = APIRouter()

@router.get("", response_model=List[schemas.EyeNodeResponse])
@router.get("/", response_model=List[schemas.EyeNodeResponse])
def list_eyes(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    db_eyes = db.query(models.EyeNode).order_by(models.EyeNode.id.asc()).all()
    results = []
    now = time.time()

    for eye in db_eyes:
        live_telemetry = HardwareState.nodes.get(eye.node_id, {})
        last_seen = live_telemetry.get("last_seen", 0)
        is_online = bool(live_telemetry.get("is_online", True)) and ((now - last_seen) < 60.0)

        results.append(schemas.EyeNodeResponse(
            id=eye.id,
            node_id=eye.node_id,
            name=eye.name,
            ip=eye.ip,
            stream_url=eye.stream_url,
            yolo_threshold=eye.yolo_threshold,
            is_active=eye.is_active,
            created_at=eye.created_at,
            is_online=is_online,
            fps=live_telemetry.get("fps", 30.0 if is_online else 0.0),
            ram_used_gb=live_telemetry.get("ram_used_gb"),
            ram_total_gb=live_telemetry.get("ram_total_gb"),
            cpu_load_pct=live_telemetry.get("cpu_load_pct"),
            gpu_load_pct=live_telemetry.get("gpu_load_pct"),
            temp_c=live_telemetry.get("temp_c"),
            link_status=live_telemetry.get("link_status", "Wi-Fi" if is_online else "Desconectado"),
            tracking_enabled=live_telemetry.get("tracking_enabled", True)
        ))
    return results

@router.post("", response_model=schemas.EyeNodeResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=schemas.EyeNodeResponse, status_code=status.HTTP_201_CREATED)
def create_eye(eye_in: schemas.EyeNodeCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    existing = db.query(models.EyeNode).filter(models.EyeNode.node_id == eye_in.node_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"El nodo Ojo '{eye_in.node_id}' ya existe.")

    eye = models.EyeNode(
        node_id=eye_in.node_id,
        name=eye_in.name,
        ip=eye_in.ip,
        stream_url=eye_in.stream_url,
        yolo_threshold=eye_in.yolo_threshold,
        is_active=eye_in.is_active
    )
    db.add(eye)
    db.commit()
    db.refresh(eye)

    HardwareState.add_log(f"👁️ Nuevo Módulo Ojo registrado: [{eye.name}] ({eye.node_id})", level="INFO", camera_module=eye.node_id)
    return schemas.EyeNodeResponse(
        id=eye.id,
        node_id=eye.node_id,
        name=eye.name,
        ip=eye.ip,
        stream_url=eye.stream_url,
        yolo_threshold=eye.yolo_threshold,
        is_active=eye.is_active,
        created_at=eye.created_at,
        is_online=False
    )

@router.put("/{node_id}", response_model=schemas.EyeNodeResponse)
def update_eye(node_id: str, eye_up: schemas.EyeNodeUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    eye = db.query(models.EyeNode).filter(models.EyeNode.node_id == node_id).first()
    if not eye:
        raise HTTPException(status_code=404, detail="Nodo Ojo no encontrado")

    # Security PIN verification for modifying hardware node properties
    if eye_up.pin and eye_up.pin != "1234":
        raise HTTPException(status_code=403, detail="PIN de seguridad inválido. Operación rechazada.")

    if eye_up.name is not None:
        eye.name = eye_up.name
    if eye_up.ip is not None:
        eye.ip = eye_up.ip
    if eye_up.stream_url is not None:
        eye.stream_url = eye_up.stream_url
    if eye_up.yolo_threshold is not None:
        eye.yolo_threshold = round(float(eye_up.yolo_threshold), 2)
    if eye_up.is_active is not None:
        eye.is_active = eye_up.is_active

    db.commit()
    db.refresh(eye)

    if eye.node_id in HardwareState.nodes:
        HardwareState.nodes[eye.node_id]["name"] = eye.name
        HardwareState.nodes[eye.node_id]["ip"] = eye.ip

    HardwareState.add_log(
        f"⚙️ Configuración actualizada para Ojo [{eye.node_id}]: Umbral YOLO {int((eye.yolo_threshold or 0.7)*100)}%, IP {eye.ip}",
        level="INFO",
        camera_module=eye.node_id
    )

    try:
        from ..mqtt.client import get_mqtt_client
        import json
        c = get_mqtt_client()
        if c:
            cfg = json.dumps({
                "node_id": eye.node_id,
                "name": eye.name,
                "confidence_threshold": eye.yolo_threshold,
                "stream_url": eye.stream_url
            })
            c.publish(f"sari/nodes/{eye.node_id}/config", cfg, qos=1, retain=True)
    except Exception as ex:
        print(f"[MQTT] Error publishing eye config update: {ex}")

    live_telemetry = HardwareState.nodes.get(eye.node_id, {})
    now = time.time()
    last_seen = live_telemetry.get("last_seen", 0)
    is_online = bool(live_telemetry.get("is_online", True)) and ((now - last_seen) < 60.0)

    return schemas.EyeNodeResponse(
        id=eye.id,
        node_id=eye.node_id,
        name=eye.name,
        ip=eye.ip,
        stream_url=eye.stream_url,
        yolo_threshold=eye.yolo_threshold,
        is_active=eye.is_active,
        created_at=eye.created_at,
        is_online=is_online,
        fps=live_telemetry.get("fps", 30.0 if is_online else 0.0),
        ram_used_gb=live_telemetry.get("ram_used_gb"),
        ram_total_gb=live_telemetry.get("ram_total_gb"),
        cpu_load_pct=live_telemetry.get("cpu_load_pct"),
        gpu_load_pct=live_telemetry.get("gpu_load_pct"),
        temp_c=live_telemetry.get("temp_c"),
        link_status=live_telemetry.get("link_status")
    )

@router.delete("/{node_id}")
def delete_eye(node_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    eye = db.query(models.EyeNode).filter(models.EyeNode.node_id == node_id).first()
    if not eye:
        raise HTTPException(status_code=404, detail="Nodo Ojo no encontrado")

    db.delete(eye)
    db.commit()
    HardwareState.add_log(f"🗑️ Módulo Ojo eliminado: [{node_id}]", level="WARN", camera_module=node_id)
    return {"status": "success", "message": f"Nodo Ojo {node_id} eliminado"}

@router.post("/test-connection")
def test_connection(req: schemas.TestConnectionRequest, current_user: dict = Depends(get_current_user)):
    target = req.target_url.strip()
    if not target.startswith("http://") and not target.startswith("https://"):
        target = f"http://{target}"

    start_t = time.time()
    try:
        res = requests.get(target, timeout=2.0, stream=True)
        latency_ms = round((time.time() - start_t) * 1000, 1)
        # Check if ok or redirect or streaming
        reachable = res.status_code in [200, 204, 301, 302]
        return {
            "reachable": reachable,
            "status_code": res.status_code,
            "latency_ms": latency_ms,
            "content_type": res.headers.get("Content-Type", "")
        }
    except Exception as e:
        latency_ms = round((time.time() - start_t) * 1000, 1)
        return {
            "reachable": False,
            "error": str(e),
            "latency_ms": latency_ms
        }

@router.get("/recordings")
def list_recordings(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.snapshot.isnot(None)
    ).order_by(models.ChatMessage.timestamp.desc()).limit(30).all()

    recordings = []
    for msg in messages:
        recordings.append({
            "id": msg.id,
            "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else "",
            "content": msg.content,
            "snapshot": msg.snapshot,
            "thread_id": msg.thread_id
        })
    return recordings

from pydantic import BaseModel, Field

class TrackingPayload(BaseModel):
    enabled: bool

class PTZPayload(BaseModel):
    action: str = Field(..., description="Direction: up, down, left, right, center, zoom_in, zoom_out, drag")
    pan_delta: Optional[float] = 0.0
    tilt_delta: Optional[float] = 0.0
    zoom_delta: Optional[float] = 0.0

@router.post("/{node_id}/tracking")
def set_eye_tracking(node_id: str, payload: TrackingPayload, current_user: dict = Depends(get_current_user)):
    if node_id in HardwareState.nodes:
        HardwareState.nodes[node_id]["tracking_enabled"] = payload.enabled
    
    HardwareState.add_log(
        f"🎯 Seguimiento automático de humanos {'ACTIVADO' if payload.enabled else 'DESACTIVADO'} para [{node_id}]",
        level="INFO",
        camera_module=node_id
    )

    try:
        from ..mqtt.client import get_mqtt_client
        import json
        c = get_mqtt_client()
        if c:
            msg = json.dumps({"node_id": node_id, "enabled": payload.enabled, "timestamp": time.time()})
            c.publish(f"sari/nodes/{node_id}/tracking", msg, qos=1, retain=True)
    except Exception as ex:
        print(f"[MQTT] Error publishing tracking state: {ex}")

    return {"status": "success", "node_id": node_id, "tracking_enabled": payload.enabled}

@router.post("/{node_id}/ptz")
def send_ptz_command(node_id: str, payload: PTZPayload, current_user: dict = Depends(get_current_user)):
    try:
        from ..mqtt.client import get_mqtt_client
        import json
        c = get_mqtt_client()
        if c:
            msg = json.dumps({
                "node_id": node_id,
                "action": payload.action,
                "pan_delta": payload.pan_delta,
                "tilt_delta": payload.tilt_delta,
                "zoom_delta": payload.zoom_delta,
                "timestamp": time.time()
            })
            c.publish(f"sari/nodes/{node_id}/ptz", msg, qos=0)
    except Exception as ex:
        print(f"[MQTT] Error publishing PTZ command: {ex}")

    return {"status": "success", "node_id": node_id, "action": payload.action}
