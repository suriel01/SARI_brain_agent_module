from sqlalchemy.orm import Session
from ..models import models
from ..schemas import schemas
import bcrypt

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# --- Users ---
def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session):
    return db.query(models.User).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        password_hash=hashed_password,
        role=user.role,
        clearance_level=user.clearance_level,
        can_create_chats=user.can_create_chats or (user.role == "admin"),
        can_delete_chats=user.can_delete_chats or (user.role == "admin"),
        can_rename_chats=user.can_rename_chats or (user.role == "admin"),
        can_control_hardware=user.can_control_hardware or (user.role == "admin"),
        can_manage_users=user.can_manage_users or (user.role == "admin")
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
        return True
    return False

# --- Chat ---
def get_user_threads(db: Session, user_id: int = None):
    return db.query(models.ChatThread).order_by(models.ChatThread.created_at.asc()).all()

def get_thread(db: Session, thread_id: int, user_id: int = None):
    return db.query(models.ChatThread).filter(models.ChatThread.id == thread_id).first()

def create_thread(db: Session, user_id: int, title: str = "Nueva Conversación"):
    db_thread = models.ChatThread(user_id=user_id, title=title)
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return db_thread

def add_message(db: Session, thread_id: int, role: str, content: str):
    db_msg = models.ChatMessage(thread_id=thread_id, role=role, content=content)
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return db_msg

def update_thread_title(db: Session, thread_id: int, new_title: str):
    thread = get_thread(db, thread_id)
    if thread:
        thread.title = new_title
        db.commit()
        db.refresh(thread)
    return thread

def delete_thread(db: Session, thread_id: int):
    thread = get_thread(db, thread_id)
    if thread:
        db.delete(thread)
        db.commit()
        return True
    return False
