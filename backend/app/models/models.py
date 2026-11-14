from sqlalchemy import JSON, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
from ..database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), default="monitor")
    clearance_level = Column(Integer, default=1)

    can_create_chats = Column(Boolean, default=False)
    can_delete_chats = Column(Boolean, default=False)
    can_rename_chats = Column(Boolean, default=False)
    can_control_hardware = Column(Boolean, default=False)
    can_manage_users = Column(Boolean, default=False)

    threads = relationship("ChatThread", back_populates="user", cascade="all, delete-orphan")

class ChatThread(Base):
    __tablename__ = "chat_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(100), default="Nueva Conversación")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="threads")
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id"))
    role = Column(String(20)) # "user", "system", "agent"
    content = Column(Text)
    snapshot = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    thread = relationship("ChatThread", back_populates="messages")

class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    module_name = Column(String(100))
    event_description = Column(Text)
    confidence = Column(Float, nullable=True)
    embedding = Column(Vector(768)) # 768 para nomic-embed-text

class EyeNode(Base):
    __tablename__ = "eye_nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    ip = Column(String(50), default="192.168.1.73")
    stream_url = Column(String(255), default="http://192.168.55.1:8080/mjpeg")
    yolo_threshold = Column(Float, default=0.70)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def _utcnow():
    from datetime import timezone

    return datetime.now(timezone.utc)


class PhysicalActionLog(Base):
    """Persistent audit trail of every physical action request (S8), including denied and failed ones."""

    __tablename__ = "physical_action_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True, nullable=False)
    actor_name = Column(String(100), nullable=False)
    channel = Column(String(30), nullable=False)
    action = Column(String(50), nullable=False)
    result = Column(String(20), nullable=False)  # success | denied | failed
    detail = Column(Text, nullable=True)


class ActuatorStateRow(Base):
    """Single-row live actuator state and alert counters (id is always 1)."""

    __tablename__ = "actuator_state"

    id = Column(Integer, primary_key=True)
    siren_active = Column(Boolean, nullable=False, default=False)
    gates_locked = Column(Boolean, nullable=False, default=False)
    alert_count = Column(Integer, nullable=False, default=0)
    last_alert_time = Column(Float, nullable=False, default=0.0)
    last_alert_thread_id = Column(Integer, nullable=True)


class NodeStatus(Base):
    """Live status and telemetry of a vision node, as last reported. ``last_seen`` mirrors ``data['last_seen']``."""

    __tablename__ = "node_status"

    node_id = Column(String(100), primary_key=True)
    data = Column(JSON, nullable=False)
    last_seen = Column(Float, nullable=True, index=True)


class OperationalLog(Base):
    """SOC operational log shown on the dashboard (24 h TTL, newest 300 kept)."""

    __tablename__ = "operational_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    message = Column(Text, nullable=False)
    level = Column(String(20), nullable=False)
    camera_module = Column(String(100), nullable=False)


class RateLimitRow(Base):
    """Login/PIN failure counters shared by every process (``key`` is ``<scope>:<key>``)."""

    __tablename__ = "rate_limit"

    key = Column(String(255), primary_key=True)
    failures = Column(JSON, nullable=False)
    locked_until = Column(Float, nullable=True)


class NodeFlags(Base):
    """Per-node flags kept apart from the telemetry (which replaces ``node_status.data``)."""

    __tablename__ = "node_flags"

    node_id = Column(String(100), primary_key=True)
    disconnect_notified = Column(Boolean, nullable=False, default=False)  # watchdog alert already sent
    tracking_enabled = Column(Boolean, nullable=True)  # operator choice; None = node default


class AlarmStateRow(Base):
    """Single-row alarm state machine status (id is always 1); see `app.domain.alarm`."""

    __tablename__ = "alarm_state"

    id = Column(Integer, primary_key=True)
    state = Column(String(20), nullable=False)
    mode = Column(String(10), nullable=True)
    since = Column(Float, nullable=False)
    deadline = Column(Float, nullable=True)
    cause = Column(String(200), nullable=False, default="")


class AlarmEventRow(Base):
    """Alarm timeline: transitions, ignored detections, failed-to-arm attempts, faults raised and cleared."""

    __tablename__ = "alarm_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(Float, nullable=False, index=True)
    kind = Column(String(30), nullable=False)
    from_state = Column(String(20), nullable=True)
    to_state = Column(String(20), nullable=True)
    cause = Column(String(200), nullable=False, default="")
    actor = Column(String(100), nullable=False, default="")


class AlarmFaultRow(Base):
    """Active supervision faults by device (a missed heartbeat); removed when the device is back."""

    __tablename__ = "alarm_fault"

    device_id = Column(String(100), primary_key=True)
    kind = Column(String(30), nullable=False)
    since = Column(Float, nullable=False)
    reason = Column(String(200), nullable=False, default="")
