"""Habitation queries and detail endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from hillcare_pipeline.db import get_db_session
from hillcare_pipeline.models import Facility, Habitation, Region, TravelTime, Underserved
from schemas import (
    HabitationItem,
    HabitationListResponse,
    NearestFacility,
    TravelTimeRange,
)

router = APIRouter(prefix="/api/v1/habitations", tags=["Habitations"])


@router.get("", response_model=HabitationListResponse)
def list_habitations(
    district_id: Optional[int] = None,
    block_id: Optional[int] = None,
    threshold: Optional[float] = None,
    mode: str = "walk",
    min_population: int = 0,
    limit: int = Query(default=100, le=500),
    cursor: Optional[int] = None,
):
    """List habitations with travel times, nearest facility, and underserved flags."""
    with get_db_session() as session:
        query = session.query(Habitation)

        if block_id:
            query = query.filter(Habitation.region_id == block_id)
        elif district_id:
            district = session.get(Region, district_id)
            if district:
                sub_ids = [r.id for r in district.children] + [district_id]
                query = query.filter(Habitation.region_id.in_(sub_ids))

        if min_population > 0:
            query = query.filter(Habitation.population >= min_population)

        if cursor:
            query = query.filter(Habitation.id > cursor)

        total_count = query.count()
        habitations = query.order_by(Habitation.id).limit(limit).all()
        hab_ids = [h.id for h in habitations]

        # Batch load latest travel times
        tt_map = {
            tt.habitation_id: tt
            for tt in session.query(TravelTime).filter(TravelTime.habitation_id.in_(hab_ids)).all()
        }

        # Batch load facility names
        fac_ids = {tt.facility_id for tt in tt_map.values() if tt.facility_id is not None}
        fac_map = {
            f.id: f for f in session.query(Facility).filter(Facility.id.in_(fac_ids)).all()
        }

        # Batch load underserved flags
        und_records = (
            session.query(Underserved).filter(Underserved.habitation_id.in_(hab_ids)).all()
        )
        und_map = {}
        for u in und_records:
            if u.habitation_id not in und_map:
                und_map[u.habitation_id] = {}
            und_map[u.habitation_id][str(int(u.threshold_min))] = u.is_underserved

        items: List[HabitationItem] = []
        for h in habitations:
            tt = tt_map.get(h.id)
            w_base = tt.walk_min if tt else 0.0
            w_low = tt.walk_min_low if tt else 0.0
            w_high = tt.walk_min_high if tt else 0.0
            hyb = tt.hybrid_min if tt else 0.0

            near_fac = None
            if tt and tt.facility_id and tt.facility_id in fac_map:
                fac = fac_map[tt.facility_id]
                near_fac = NearestFacility(id=fac.id, name=fac.name, tier=fac.tier)

            flags = []
            if h.loc_quality != "gps_verified":
                flags.append(h.loc_quality)

            item = HabitationItem(
                id=h.id,
                name=h.name,
                block=h.region.name if h.region else None,
                lat=h.lat,
                lon=h.lon,
                elevation_m=h.elevation_m,
                population=h.population,
                sc_pct=h.sc_pct,
                st_pct=h.st_pct,
                travel_time_min=TravelTimeRange(base=w_base, low=w_low, high=w_high),
                hybrid_time_min=hyb,
                nearest_facility=near_fac,
                underserved=und_map.get(h.id, {"30": True, "60": True, "90": True}),
                quality_flags=flags,
            )

            # Apply threshold filter if requested
            if threshold is not None:
                if item.travel_time_min.base <= threshold:
                    continue

            items.append(item)

        next_c = str(habitations[-1].id) if habitations and len(habitations) == limit else None

        return HabitationListResponse(
            run_id="run_baseline_current",
            total_count=total_count,
            items=items,
            next_cursor=next_c,
        )


@router.get("/{habitation_id}", response_model=HabitationItem)
def get_habitation_details(habitation_id: int):
    """Retrieve detailed travel time and demographics for a specific habitation."""
    with get_db_session() as session:
        h = session.get(Habitation, habitation_id)
        if not h:
            raise HTTPException(status_code=404, detail="Habitation not found")

        tt = session.query(TravelTime).filter_by(habitation_id=h.id).first()
        near_fac = None
        if tt and tt.facility_id:
            fac = session.get(Facility, tt.facility_id)
            if fac:
                near_fac = NearestFacility(id=fac.id, name=fac.name, tier=fac.tier)

        und_records = session.query(Underserved).filter_by(habitation_id=h.id).all()
        und_flags = {str(int(u.threshold_min)): u.is_underserved for u in und_records}

        return HabitationItem(
            id=h.id,
            name=h.name,
            block=h.region.name if h.region else None,
            lat=h.lat,
            lon=h.lon,
            elevation_m=h.elevation_m,
            population=h.population,
            sc_pct=h.sc_pct,
            st_pct=h.st_pct,
            travel_time_min=TravelTimeRange(
                base=tt.walk_min if tt else 0.0,
                low=tt.walk_min_low if tt else 0.0,
                high=tt.walk_min_high if tt else 0.0,
            ),
            hybrid_time_min=tt.hybrid_min if tt else 0.0,
            nearest_facility=near_fac,
            underserved=und_flags or {"30": True, "60": True, "90": True},
            quality_flags=[h.loc_quality],
        )
