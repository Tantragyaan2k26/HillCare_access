"""Facility listing and query router."""

from typing import List, Optional
from fastapi import APIRouter
from sqlalchemy.orm import Session

from hillcare_pipeline.db import get_db_session
from hillcare_pipeline.models import Facility, Region
from schemas import FacilityItem

router = APIRouter(prefix="/api/v1/facilities", tags=["Facilities"])


@router.get("", response_model=List[FacilityItem])
def list_facilities(
    district_id: Optional[int] = None,
    tier: Optional[str] = None,
    functional_only: bool = True,
):
    """List facilities filtered by district, tier (DH, CHC, PHC, HWC), and functional status."""
    with get_db_session() as session:
        query = session.query(Facility)

        if district_id:
            district = session.get(Region, district_id)
            if district:
                sub_ids = [r.id for r in district.children] + [district_id]
                query = query.filter(Facility.region_id.in_(sub_ids))

        if tier:
            query = query.filter(Facility.tier == tier.upper())

        if functional_only:
            query = query.filter(Facility.is_functional == True)

        facs = query.order_by(Facility.id).all()
        return [
            FacilityItem(
                id=f.id,
                name=f.name,
                tier=f.tier,
                lat=f.lat,
                lon=f.lon,
                elevation_m=f.elevation_m,
                region_id=f.region_id,
                is_functional=f.is_functional,
                doctor_count=f.doctor_count,
                bed_count=f.bed_count,
            )
            for f in facs
        ]
