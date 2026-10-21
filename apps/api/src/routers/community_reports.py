"""Public community submissions and token-protected review operations."""

from __future__ import annotations

import hmac
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from community_store import (
    CommunityReport,
    CommunityReportHistory,
    get_community_session,
    utc_now,
)
from schemas_community import (
    CommunityHistoryItem,
    CommunityReportCreate,
    CommunityReportPublicStatus,
    CommunityReportReceipt,
    CommunityReviewUpdate,
)

router = APIRouter(prefix="/api/v1/community-reports", tags=["Community reports"])


def _receipt(report: CommunityReport) -> dict:
    return {
        "id": report.id,
        "status": report.status,
        "district": report.district,
        "category": report.category,
        "submitted_at": report.submitted_at,
        "observed_on": report.observed_on,
    }


def _require_reviewer(x_reviewer_token: str | None = Header(default=None)) -> None:
    configured = os.getenv("HILLCARE_REVIEWER_TOKEN")
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review actions are disabled until HILLCARE_REVIEWER_TOKEN is configured.",
        )
    if not x_reviewer_token or not hmac.compare_digest(x_reviewer_token, configured):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer authorization failed.")


@router.post("", response_model=CommunityReportReceipt, status_code=status.HTTP_201_CREATED)
def submit_report(
    payload: CommunityReportCreate,
    session: Session = Depends(get_community_session),
):
    if payload.based_on_report_id and session.get(CommunityReport, payload.based_on_report_id) is None:
        raise HTTPException(status_code=404, detail="Referenced report does not exist.")
    report = CommunityReport(
        id=str(uuid4()),
        category=payload.category,
        district=payload.district,
        latitude=payload.latitude,
        longitude=payload.longitude,
        subject=payload.subject.strip(),
        description=payload.description.strip(),
        evidence_source=payload.evidence_source.strip(),
        evidence_url=str(payload.evidence_url) if payload.evidence_url else None,
        observed_on=payload.observed_on,
        based_on_report_id=payload.based_on_report_id,
        status="pending",
        submitted_at=utc_now(),
    )
    session.add(report)
    session.add(CommunityReportHistory(
        report_id=report.id,
        action="submitted",
        previous_status=None,
        new_status="pending",
        note="Submitted for review; source data unchanged.",
        changed_at=utc_now(),
    ))
    session.flush()
    return _receipt(report)


@router.get("/{report_id}", response_model=CommunityReportPublicStatus)
def get_report_status(
    report_id: str,
    session: Session = Depends(get_community_session),
):
    report = session.get(CommunityReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Community report not found.")
    return _receipt(report)


@router.get("", dependencies=[Depends(_require_reviewer)])
def list_reports(
    report_status: str | None = None,
    district: str | None = None,
    session: Session = Depends(get_community_session),
):
    statement = select(CommunityReport).order_by(CommunityReport.submitted_at.desc())
    if report_status:
        statement = statement.where(CommunityReport.status == report_status)
    if district:
        statement = statement.where(CommunityReport.district == district)
    return [
        {
            **_receipt(report),
            "latitude": report.latitude,
            "longitude": report.longitude,
            "subject": report.subject,
            "description": report.description,
            "evidence_source": report.evidence_source,
            "evidence_url": report.evidence_url,
            "based_on_report_id": report.based_on_report_id,
        }
        for report in session.scalars(statement)
    ]


@router.patch("/{report_id}", dependencies=[Depends(_require_reviewer)])
def review_report(
    report_id: str,
    payload: CommunityReviewUpdate,
    session: Session = Depends(get_community_session),
):
    report = session.get(CommunityReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Community report not found.")
    previous = report.status
    report.status = payload.status
    session.add(CommunityReportHistory(
        report_id=report.id,
        action="reviewed",
        previous_status=previous,
        new_status=payload.status,
        note=payload.note.strip(),
        changed_at=utc_now(),
    ))
    session.flush()
    return _receipt(report)


@router.get("/{report_id}/history", response_model=list[CommunityHistoryItem],
            dependencies=[Depends(_require_reviewer)])
def get_report_history(
    report_id: str,
    session: Session = Depends(get_community_session),
):
    if session.get(CommunityReport, report_id) is None:
        raise HTTPException(status_code=404, detail="Community report not found.")
    return session.scalars(
        select(CommunityReportHistory)
        .where(CommunityReportHistory.report_id == report_id)
        .order_by(CommunityReportHistory.id)
    ).all()
