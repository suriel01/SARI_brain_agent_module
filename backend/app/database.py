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

# Bound how long a hung database can stall callers (alarm paths run DB steps before the siren).
# A statement_timeout is deliberately not set: migrations wait on pg_advisory_lock during concurrent starts.
PG_CONNECT_TIMEOUT_S = 3


def engine_options(url: str) -> dict:
    opts = {"pool_pre_ping": True}
    if url.startswith("postgresql"):
        opts["connect_args"] = {"connect_timeout": PG_CONNECT_TIMEOUT_S}
    return opts


engine = create_engine(DATABASE_URL, **engine_options(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
