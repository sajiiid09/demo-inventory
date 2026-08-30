"""Bring the database up on startup: create it, migrate it, seed it.

Running the API is the only step. On boot it will, in order:

  1. wait for Postgres to accept connections,
  2. CREATE DATABASE <name> if that database does not exist yet,
  3. run `alembic upgrade head` so every table, index and trigger exists,
  4. make sure the demo staff logins exist, and load the demo portfolio
     if the database is still empty.

Every step is idempotent: a second boot finds nothing to do and says so.
Each step has its own switch in app/config.py (AUTO_CREATE_DATABASE,
AUTO_MIGRATE, AUTO_SEED) for an environment that migrates out of band.

Migrations stay the single source of truth for the schema — this module runs
Alembic, it never calls `Base.metadata.create_all()`. The triggers and the
partial unique index only exist in revision 0001, so a metadata-only schema
would silently be the wrong schema (DATABASE.md §4).
"""

import logging
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.config import settings

log = logging.getLogger("microloan.bootstrap")

API_ROOT = Path(__file__).resolve().parents[1]  # the directory holding alembic.ini


def _maintenance_engine(url):
    """An engine on the `postgres` maintenance database, in autocommit —
    CREATE DATABASE cannot run inside a transaction block."""
    admin_url = url.set(database="postgres")
    return create_engine(
        admin_url.render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )


def wait_for_postgres(url, timeout: int) -> None:
    """Block until the server answers, or give up with the real error.

    Compose already gates the API on a healthcheck; this covers the native
    run, where `docker compose up -d postgres` may still be starting.
    """
    engine = _maintenance_engine(url)
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return
        except OperationalError:
            if time.monotonic() >= deadline:
                engine.dispose()
                raise
            if attempt == 1:
                log.info("waiting for postgres at %s:%s …", url.host, url.port)
            time.sleep(1)


def ensure_database(url) -> bool:
    """CREATE DATABASE if it is missing. True if it was created just now."""
    engine = _maintenance_engine(url)
    try:
        with engine.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if exists:
                return False
            # The name comes from our own configuration, but quote it anyway.
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
            log.info("created database %r", url.database)
            return True
    except ProgrammingError as exc:
        # Another process (a second uvicorn worker) won the race — fine.
        if "duplicate_database" in str(exc.orig):
            return False
        raise
    finally:
        engine.dispose()


def run_migrations() -> str:
    """`alembic upgrade head`, in-process. Returns the revision now applied."""
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    # env.py reads DATABASE_URL from app settings; keep it from re-configuring
    # the logging stack out from under uvicorn.
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")

    from app.db import engine  # imported late: settings must be read first

    with engine.connect() as conn:
        return conn.scalar(text("SELECT version_num FROM alembic_version")) or "none"


def prepare_database() -> None:
    """The whole boot sequence. Safe to run on every start."""
    url = make_url(settings.database_url)

    wait_for_postgres(url, settings.db_wait_seconds)

    if settings.auto_create_database:
        ensure_database(url)

    if settings.auto_migrate:
        revision = run_migrations()
        log.info("schema is at revision %s", revision)

    if settings.auto_seed:
        from app.seeds import ensure_seeded

        log.info("seed: %s", ensure_seeded())
