"""Engine and session factory. Services own transactions (one service call =
one transaction); this module only provides sessions."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    """FastAPI dependency yielding a session; the caller's service commits."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
