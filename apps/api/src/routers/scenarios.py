"""Scenario workspace endpoints for planners."""

import json
import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from hillcare_pipeline.db import get_db_session
from hillcare_pipeline.models import Region, Scenario
from hillcare_pipeline.runner import run_pipeline_for_district
from auth import AuthUser, require_role
from schemas import ScenarioCreateRequest, ScenarioResponse

router = APIRouter(prefix="/api/v1/scenarios", tags=["Scenarios"])


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    payload: ScenarioCreateRequest,
    user: AuthUser = Depends(require_role("planner")),
):
    """Submit a what-if planning scenario (e.g. hypothetical facility, custom threshold)."""
    scenario_id = f"scen_{uuid.uuid4().hex[:12]}"

    with get_db_session() as session:
        region = session.get(Region, payload.region_id)
        if not region:
            raise HTTPException(status_code=404, detail="Region not found")

        # District resolution: if block passed, get parent district
        dist_id = region.parent_id if region.level == "block" and region.parent_id else region.id

        scen = Scenario(
            id=scenario_id,
            owner_id=user.id,
            name=payload.name,
            params_json=json.dumps(payload.model_dump()),
            status="running",
        )
        session.add(scen)
        session.flush()

        # Run localized scenario simulation
        run_res = run_pipeline_for_district(
            session=session,
            district_id=dist_id,
            run_id=f"run_scen_{scenario_id}",
            tier=payload.tier,
            thresholds=[payload.threshold_min],
            k_candidates=payload.k,
        )

        scen.status = "succeeded"
        scen.run_id = run_res["run_id"]
        session.flush()

        return ScenarioResponse(
            id=scen.id,
            owner_id=scen.owner_id,
            name=scen.name,
            status=scen.status,
            params=payload.model_dump(),
            run_id=scen.run_id,
            result=run_res,
        )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: str,
    user: AuthUser = Depends(require_role("planner")),
):
    """Retrieve status and results of a planner scenario."""
    with get_db_session() as session:
        scen = session.get(Scenario, scenario_id)
        if not scen:
            raise HTTPException(status_code=404, detail="Scenario not found")

        # Check ownership unless analyst/admin
        if scen.owner_id != user.id and user.role not in ["analyst", "admin"]:
            raise HTTPException(status_code=403, detail="Forbidden: You do not own this scenario.")

        params = json.loads(scen.params_json) if scen.params_json else {}

        return ScenarioResponse(
            id=scen.id,
            owner_id=scen.owner_id,
            name=scen.name,
            status=scen.status,
            params=params,
            run_id=scen.run_id,
        )


@router.delete("/{scenario_id}")
def delete_scenario(
    scenario_id: str,
    user: AuthUser = Depends(require_role("planner")),
):
    """Delete a scenario."""
    with get_db_session() as session:
        scen = session.get(Scenario, scenario_id)
        if not scen:
            raise HTTPException(status_code=404, detail="Scenario not found")

        if scen.owner_id != user.id and user.role not in ["analyst", "admin"]:
            raise HTTPException(status_code=403, detail="Forbidden: You do not own this scenario.")

        session.delete(scen)
        return {"status": "deleted", "id": scenario_id}
