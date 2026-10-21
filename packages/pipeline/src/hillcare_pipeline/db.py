"""Database connection, engine initialization, and session management."""

from __future__ import annotations
import os
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from hillcare_pipeline.models import Base

DEFAULT_DB_PATH = Path("d:/GeoAI/data/hillcare.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

# For SQLite, check same thread
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine=engine) -> None:
    """Create all tables in the target database."""
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=target_engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
