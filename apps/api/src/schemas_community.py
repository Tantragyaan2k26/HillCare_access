"""Validated request and response contracts for community contributions."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

DistrictName = Literal["Chamoli", "Pithoragarh", "Rudraprayag"]
ReportCategory = Literal[
    "missing_habitation",
    "missing_facility",
    "road_update",
    "correction",
    "facility_closure",
    "access_barrier",
]
ReportStatus = Literal[
    "pending",
    "community-confirmed",
    "officially-confirmed",
    "rejected",
    "needs-recheck",
]


class CommunityReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ReportCategory
    district: DistrictName
    latitude: float = Field(ge=6.0, le=38.0)
    longitude: float = Field(ge=68.0, le=98.0)
    subject: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    evidence_source: str = Field(min_length=3, max_length=240)
    evidence_url: HttpUrl | None = None
    observed_on: date | None = None
    based_on_report_id: str | None = Field(default=None, max_length=36)


class CommunityReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReportStatus
    note: str = Field(min_length=3, max_length=2000)


class CommunityReportReceipt(BaseModel):
    id: str
    status: str
    district: str
    category: str
    submitted_at: datetime
    observed_on: date | None


class CommunityReportPublicStatus(CommunityReportReceipt):
    pass


class CommunityHistoryItem(BaseModel):
    action: str
    previous_status: str | None
    new_status: str
    note: str | None
    changed_at: datetime
