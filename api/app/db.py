"""Engine and session factory. Services own transactions (one service call =
one transaction); this module only provides sessions."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    """FastAPI dependency yielding a session.

    One request = one transaction: the session's implicit transaction starts
    with the first statement (usually loading the current user) and services
    commit exactly once, at the end. If anything raises, nothing was committed
    and close() discards the work — all-or-nothing without ceremony.
    """
    session: Session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
