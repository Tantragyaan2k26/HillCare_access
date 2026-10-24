"""Candidate site query router."""

import json

from fastapi import APIRouter, Query
from hillcare_pipeline.db import get_db_session
from hillcare_pipeline.models import CandidateSiteRecord, Run
from schemas import CandidateItem, CandidateListResponse

router = APIRouter(prefix="/api/v1/candidates", tags=["Candidates"])


@router.get("", response_model=CandidateListResponse)
def list_candidates(
    district: str = "pithoragarh",
    objective: str = "max_new_coverage",
    limit: int = Query(default=10, le=50),
):
    """List ranked candidate facility sites with newly covered population and equity metrics."""
    with get_db_session() as session:
        run = (
            session.query(Run)
            .filter(Run.id.like(f"%{district.lower()}%"))
            .filter(Run.status == "succeeded")
            .order_by(Run.created_at.desc())
            .first()
        )
        if not run:
            run = session.query(Run).filter_by(status="succeeded").order_by(Run.created_at.desc()).first()

        if not run:
            return CandidateListResponse(run_id="none", objective=objective, candidates=[])

        query = session.query(CandidateSiteRecord).filter_by(run_id=run.id)

        if objective == "equity_weighted":
            query = query.order_by(CandidateSiteRecord.equity_score.desc())
        elif objective == "min_mean_time":
            query = query.order_by(CandidateSiteRecord.mean_time_delta.desc())
        else:
            query = query.order_by(CandidateSiteRecord.rank.asc())

        db_candidates = query.limit(limit).all()

        items = []
        for c in db_candidates:
            feas = json.loads(c.feasibility_json) if c.feasibility_json else {}
            items.append(
                CandidateItem(
                    id=c.id,
                    rank=c.rank,
                    lat=c.lat,
                    lon=c.lon,
                    gain_pop=c.gain_pop,
                    mean_time_delta=c.mean_time_delta,
                    equity_score=c.equity_score,
                    feasibility=feas,
                )
            )

        return CandidateListResponse(
            run_id=run.id,
            objective=objective,
            candidates=items,
        )
