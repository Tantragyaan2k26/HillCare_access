"""Persistent community report storage kept separate from source datasets."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class CommunityBase(DeclarativeBase):
    pass


class CommunityReport(CommunityBase):
    __tablename__ = "community_report"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    district: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(240), nullable=False)
    evidence_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    observed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    based_on_report_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommunityReportHistory(CommunityBase):
    __tablename__ = "community_report_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("community_report.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _database_url() -> str:
    default = Path(__file__).resolve().parents[3] / "data" / "community_reports.sqlite3"
    return os.getenv("HILLCARE_COMMUNITY_DATABASE_URL", f"sqlite:///{default.as_posix()}")


_url = _database_url()
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=_connect_args, future=True)
CommunitySession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_community_session() -> Iterator:
    CommunityBase.metadata.create_all(bind=engine)
    session = CommunitySession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def utc_now() -> datetime:
    return datetime.now(UTC)
