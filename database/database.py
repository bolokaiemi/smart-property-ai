"""
SQLAlchemy database configuration.

File:
    database/database.py
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from config import settings


class Base(DeclarativeBase):
    """Base class inherited by all SQLAlchemy models."""

    pass


engine_options = {
    "pool_pre_ping": True,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {
        "check_same_thread": False,
    }


engine = create_engine(
    settings.DATABASE_URL,
    **engine_options,
)


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    Provide one database session per request.

    Usage:

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """

    database_session = SessionLocal()

    try:
        yield database_session
    finally:
        database_session.close()


def create_database_tables() -> None:
    """Create database tables that do not already exist."""

    # Import models here so SQLAlchemy registers them before
    # Base.metadata.create_all() runs.
    from database import models  # noqa: F401

    Base.metadata.create_all(
        bind=engine
    )


def drop_database_tables() -> None:
    """
    Drop all application tables.

    Use only in an isolated test database.
    """

    Base.metadata.drop_all(
        bind=engine
    )