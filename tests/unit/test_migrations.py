"""T13: schema is owned by Alembic; existing deployments are stamped without losing data."""
import pytest
from sqlalchemy import create_engine, inspect, text

APP_TABLES = {"users", "chat_threads", "chat_messages", "event_logs", "eye_nodes", "physical_action_log"}


@pytest.fixture
def fresh_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/migr.db")
    yield engine
    engine.dispose()


def _version(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _head():
    from alembic.script import ScriptDirectory

    from app.main import alembic_config

    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def test_fresh_database_is_created_by_migrations(fresh_engine):
    from app.main import init_db

    init_db(bind=fresh_engine)
    tables = set(inspect(fresh_engine).get_table_names())
    assert APP_TABLES <= tables
    assert "alembic_version" in tables
    assert _version(fresh_engine) == _head()


def test_init_db_is_idempotent(fresh_engine):
    from app.main import init_db

    init_db(bind=fresh_engine)
    init_db(bind=fresh_engine)
    assert _version(fresh_engine) == _head()


def test_existing_deployment_is_stamped_and_keeps_data(fresh_engine):
    """A volume created by the old create_all (no alembic_version, possibly missing newer tables)."""
    from app.main import init_db
    from app.models import models

    legacy = [t for name, t in models.Base.metadata.tables.items() if name != "physical_action_log"]
    models.Base.metadata.create_all(bind=fresh_engine, tables=legacy)
    with fresh_engine.begin() as conn:
        conn.execute(text("INSERT INTO users (username, password_hash, role, clearance_level, can_control_hardware) "
                          "VALUES ('legacy_admin', 'hash', 'admin', 5, 1)"))
        conn.execute(text("INSERT INTO chat_threads (user_id, title) VALUES (1, 'old thread')"))

    init_db(bind=fresh_engine)

    assert _version(fresh_engine) == _head()
    assert APP_TABLES <= set(inspect(fresh_engine).get_table_names())
    with fresh_engine.connect() as conn:
        assert conn.execute(text("SELECT username, role, can_control_hardware FROM users")).all() == [
            ("legacy_admin", "admin", 1)]
        assert conn.execute(text("SELECT title FROM chat_threads")).scalar() == "old thread"


def test_baseline_migration_matches_models(fresh_engine):
    """Autogenerate finds no difference between the migrated schema and the models."""
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    from app.main import init_db
    from app.models import models

    init_db(bind=fresh_engine)
    with fresh_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), models.Base.metadata)

    def _sqlite_vector_reflection(entry):
        # SQLite reflects pgvector's VECTOR(768) as NUMERIC(768); the column itself is identical.
        return isinstance(entry, list) and entry[0][0] == "modify_type" and entry[0][2:4] == ("event_logs", "embedding")

    assert [d for d in diff if not _sqlite_vector_reflection(d)] == []


def test_app_startup_still_seeds_admin(client):
    """Previous behaviour: startup (init_db + seed) leaves a working admin account."""
    from app.crud import crud
    from app.database import SessionLocal
    from app.main import init_db, seed_initial_data

    init_db()
    seed_initial_data()
    db = SessionLocal()
    try:
        assert crud.get_user_by_username(db, "admin").role == "admin"
    finally:
        db.close()
