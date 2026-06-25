"""Database engine, session, and declarative base."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def _normalize_db_url(url: str) -> str:
    """Hosting platforms often hand out ``postgres://`` / ``postgresql://`` URLs,
    which SQLAlchemy maps to the (uninstalled) psycopg2 driver. We ship psycopg
    v3, so rewrite to the explicit ``postgresql+psycopg://`` dialect.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _normalize_db_url(settings.database_url)

# SQLite needs check_same_thread disabled for FastAPI's threaded request model.
connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Imports models so they register on Base.metadata."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
