import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


def normalize_database_url(url: str) -> str:
    """SQLAlchemy 2.1 maps bare postgresql:// to psycopg 3; this project ships psycopg2."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


DATABASE_URL = normalize_database_url(os.environ.get("DATABASE_URL", "sqlite:///./sari.db"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
