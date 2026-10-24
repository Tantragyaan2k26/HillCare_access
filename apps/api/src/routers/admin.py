"""Admin management endpoints for data ingestion, runs, and data issues."""

from pathlib import Path

from auth import AuthUser, require_role
from fastapi import APIRouter, Depends, HTTPException
from hillcare_pipeline.db import get_db_session
from hillcare_pipeline.ingest import ingest_district_fixture
from hillcare_pipeline.models import DataIssue, Region
from hillcare_pipeline.runner import run_pipeline_for_district

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.post("/ingest")
def trigger_ingest(
    district_name: str = "pithoragarh",
    user: AuthUser = Depends(require_role("admin")),  # noqa: B008
):
    """Trigger data ingestion for a district fixture."""
    fixture_path = Path(f"d:/GeoAI/data/sample/{district_name.lower()}_sample.json")
    if not fixture_path.exists():
        raise HTTPException(status_code=404, detail=f"Fixture file not found: {fixture_path.name}")

    with get_db_session() as session:
        summary = ingest_district_fixture(session, fixture_path)
        return {"status": "ingested", "summary": summary}


@router.post("/runs")
def trigger_run(
    district_name: str = "pithoragarh",
    tier: str = "PHC",
    user: AuthUser = Depends(require_role("admin")),  # noqa: B008
):
    """Trigger a full pipeline run for a district."""
    with get_db_session() as session:
        district = (
            session.query(Region)
            .filter(Region.name.ilike(f"%{district_name}%"))
            .filter(Region.level == "district")
            .first()
        )
        if not district:
            raise HTTPException(status_code=404, detail=f"District '{district_name}' not found")

        run_res = run_pipeline_for_district(
            session=session,
            district_id=district.id,
            tier=tier,
            thresholds=[30.0, 60.0, 90.0],
            k_candidates=5,
        )
        return {"status": "succeeded", "result": run_res}


@router.get("/data-issues")
def list_data_issues(
    status: str | None = None,
    user: AuthUser = Depends(require_role("admin")),  # noqa: B008
):
    """List data validation anomalies logged during ingestion."""
    with get_db_session() as session:
        query = session.query(DataIssue)
        if status:
            query = query.filter(DataIssue.status == status)
        issues = query.all()
        return [
            {
                "id": i.id,
                "snapshot_id": i.snapshot_id,
                "entity": i.entity,
                "ref": i.ref,
                "issue_type": i.issue_type,
                "status": i.status,
                "details": i.details,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in issues
        ]
