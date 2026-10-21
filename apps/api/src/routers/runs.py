"""Published runs and reproducibility metadata router."""

import json
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from hillcare_pipeline.db import get_db_session
from hillcare_pipeline.models import Run

router = APIRouter(prefix="/api/v1/runs", tags=["Runs"])


@router.get("/current")
def get_current_run(district: str = "pithoragarh"):
    """Get metadata, parameters, and reproducibility hashes for the current published run."""
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
            raise HTTPException(status_code=404, detail="No published run found")

        params = json.loads(run.params_json) if run.params_json else {}

        return {
            "run_id": run.id,
            "kind": run.kind,
            "status": run.status,
            "code_sha": run.code_sha,
            "image_digest": run.image_digest,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "parameters": params,
        }
