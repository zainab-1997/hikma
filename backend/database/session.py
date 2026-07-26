"""SQLAlchemy engine/session setup and database initialization.

No migration framework (e.g. Alembic) is in place yet, so a plain `create_all()` is used
at this stage. This module is deliberately isolated — init_db() is the only place table
creation happens — so it can be swapped for Alembic-driven migrations later without
touching model definitions or repository code.
"""

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings

# Additive-only columns that a database created before this column existed needs backfilled.
# create_all() only creates missing TABLES, never alters an existing one — this is the
# stopgap for that gap until Alembic replaces init_db() entirely. Remove an entry once
# every environment has been confirmed to have picked it up.
_ADDITIVE_ORDER_COLUMNS = [
    ("email_status", "VARCHAR(16)"),
    ("last_email_sent_at", "DATETIME"),
]


def _ensure_sqlite_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    db_path = database_url.removeprefix("sqlite:///")
    if db_path and db_path != ":memory:":
        Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def _build_engine(database_url: str):
    _ensure_sqlite_directory(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    return engine


def get_engine(database_url: str | None = None):
    """Pass database_url explicitly in tests to use a temporary SQLite file instead of
    the real, settings-configured app.db."""
    url = database_url if database_url is not None else get_settings().database_url
    return _build_engine(url)


def get_session_factory(database_url: str | None = None) -> sessionmaker:
    return sessionmaker(bind=get_engine(database_url), autoflush=False, expire_on_commit=False)


def _apply_additive_order_columns(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as connection:
        existing_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(orders)"))}
        for column_name, column_type in _ADDITIVE_ORDER_COLUMNS:
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE orders ADD COLUMN {column_name} {column_type}"))
        connection.commit()


def init_db(database_url: str | None = None) -> None:
    """Create all tables if they don't already exist, then backfill any additive columns
    onto tables that already existed from before those columns were added. Safe to call
    multiple times."""
    from database import models  # local import: avoids a module import cycle at startup

    engine = get_engine(database_url)
    models.Base.metadata.create_all(bind=engine)
    _apply_additive_order_columns(engine)


def check_database(database_url: str | None = None) -> bool:
    """Perform a lightweight read/write-capability check without changing application data."""
    with get_engine(database_url).connect() as connection:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        connection.execute(text("SELECT 1"))
        if connection.in_transaction():
            connection.rollback()
    return True


@contextmanager
def session_scope(database_url: str | None = None):
    """Transactional scope: commits on success, rolls back and re-raises on any error."""
    session: Session = get_session_factory(database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
