from app.database import normalize_database_url


def test_bare_postgresql_url_uses_installed_psycopg2_driver():
    assert normalize_database_url("postgresql://u:p@db:5432/x") == "postgresql+psycopg2://u:p@db:5432/x"
    assert normalize_database_url("postgres://u:p@db/x") == "postgresql+psycopg2://u:p@db/x"


def test_explicit_driver_and_sqlite_are_untouched():
    assert normalize_database_url("postgresql+psycopg2://u@db/x") == "postgresql+psycopg2://u@db/x"
    assert normalize_database_url("sqlite:///./sari.db") == "sqlite:///./sari.db"
