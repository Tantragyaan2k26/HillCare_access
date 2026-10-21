"""Regions and regional accessibility summary endpoints."""

import numpy as np
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from hillcare_pipeline.db import get_db_session
from hillcare_pipeline.models import Facility, Habitation, Region, TravelTime, Underserved
from schemas import RegionSummary

router = APIRouter(prefix="/api/v1/regions", tags=["Regions"])


@router.get("")
def list_regions(level: Optional[str] = None, parent_id: Optional[int] = None):
    """List regions with optional level ('state', 'district', 'block') and parent filter."""
    with get_db_session() as session:
        query = session.query(Region)
        if level:
            query = query.filter(Region.level == level)
        if parent_id is not None:
            query = query.filter(Region.parent_id == parent_id)
        regions = query.all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "level": r.level,
                "lgd_code": r.lgd_code,
                "parent_id": r.parent_id,
            }
            for r in regions
        ]


@router.get("/{region_id}/summary", response_model=RegionSummary)
def get_region_summary(region_id: int):
    """Get population and travel time accessibility statistics for a district or block."""
    with get_db_session() as session:
        region = session.get(Region, region_id)
        if not region:
            raise HTTPException(status_code=404, detail="Region not found")

        # Sub-regions (blocks if district)
        sub_ids = [r.id for r in region.children] + [region.id]
        habs = session.query(Habitation).filter(Habitation.region_id.in_(sub_ids)).all()
        hab_ids = [h.id for h in habs]

        fac_count = (
            session.query(Facility)
            .filter(Facility.region_id.in_(sub_ids))
            .filter(Facility.is_functional == True)
            .count()
        )

        total_pop = sum(h.population for h in habs)
        total_habs = len(habs)

        # Query travel times from latest run
        tt_records = session.query(TravelTime).filter(TravelTime.habitation_id.in_(hab_ids)).all()
        walk_times = [tt.walk_min for tt in tt_records if tt.walk_min < 900]

        mean_time = float(np.mean(walk_times)) if walk_times else 0.0
        median_time = float(np.median(walk_times)) if walk_times else 0.0

        # Underserved percentages at 30, 60, 90
        def get_underserved_pct(threshold: float) -> float:
            und_habs = (
                session.query(Underserved)
                .filter(Underserved.habitation_id.in_(hab_ids))
                .filter(Underserved.threshold_min == threshold)
                .filter(Underserved.is_underserved == True)
                .all()
            )
            und_hids = {u.habitation_id for u in und_habs}
            und_pop = sum(h.population for h in habs if h.id in und_hids)
            return round((und_pop / total_pop * 100.0), 1) if total_pop > 0 else 0.0

        return RegionSummary(
            region_id=region.id,
            region_name=region.name,
            level=region.level,
            total_population=total_pop,
            total_habitations=total_habs,
            mean_travel_time_min=round(mean_time, 1),
            median_travel_time_min=round(median_time, 1),
            underserved_pct_30min=get_underserved_pct(30.0),
            underserved_pct_60min=get_underserved_pct(60.0),
            underserved_pct_90min=get_underserved_pct(90.0),
            functional_facilities_count=fac_count,
        )
