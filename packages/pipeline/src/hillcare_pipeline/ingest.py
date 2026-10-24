"""Data ingestion and validation service.

Loads raw geojson/json fixtures into database tables, validates coordinates and
demographics, logs anomalies into the data_issue table, and records data snapshots.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from hillcare_pipeline.models import (
    DataIssue,
    DataSnapshot,
    Facility,
    Habitation,
    Region,
)

# Uttarakhand bounding box roughly: Lat 28.5 to 31.5, Lon 77.5 to 81.2
UTTARAKHAND_LAT_RANGE = (28.0, 32.0)
UTTARAKHAND_LON_RANGE = (77.0, 82.0)


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def ingest_district_fixture(session: Session, fixture_path: Path) -> dict[str, int]:
    """Ingest a district sample fixture file into database.

    Args:
        session: Active SQLAlchemy database session.
        fixture_path: Path to the district JSON file.

    Returns:
        Summary dict of ingested entity counts and detected issues.
    """
    with open(fixture_path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    file_hash = compute_file_sha256(fixture_path)
    dist_info = data["district"]
    dist_name = dist_info["name"]
    dist_id = dist_info["id"]

    # 1. Record Data Snapshot
    snapshot_id = f"snap_{dist_name.lower()}_{file_hash[:12]}"
    snapshot = session.get(DataSnapshot, snapshot_id)
    if not snapshot:
        snapshot = DataSnapshot(
            id=snapshot_id,
            source=f"Uttarakhand Census/HMIS Pilot - {dist_name}",
            version="2026.10",
            sha256=file_hash,
            licence="Open Government Data (OGD) India / OSM ODbL",
        )
        session.add(snapshot)
        session.flush()

    # 2. Ingest District Region
    dist_region = session.get(Region, dist_id)
    if not dist_region:
        dist_region = Region(
            id=dist_id,
            level="district",
            lgd_code=dist_info.get("lgd_code"),
            name=dist_name,
            parent_id=None,
        )
        session.add(dist_region)
        session.flush()

    # 3. Ingest Block Regions
    block_map: dict[str, Region] = {}
    for b_idx, block_name in enumerate(dist_info.get("blocks", [])):
        block_id = dist_id * 100 + b_idx + 1
        block_region = session.get(Region, block_id)
        if not block_region:
            block_region = Region(
                id=block_id,
                level="block",
                lgd_code=dist_info.get("lgd_code", 0) * 10 + b_idx + 1,
                name=block_name,
                parent_id=dist_id,
            )
            session.add(block_region)
            session.flush()
        block_map[block_name] = block_region

    # 4. Ingest Habitations with Validation
    hab_count = 0
    issue_count = 0

    for hab_dict in data.get("habitations", []):
        hid = hab_dict["id"]
        lat = hab_dict["lat"]
        lon = hab_dict["lon"]
        pop = hab_dict["population"]
        sc = hab_dict.get("sc_pct", 0.0)
        st = hab_dict.get("st_pct", 0.0)

        # Coordinate Validation
        if not (UTTARAKHAND_LAT_RANGE[0] <= lat <= UTTARAKHAND_LAT_RANGE[1] and
                UTTARAKHAND_LON_RANGE[0] <= lon <= UTTARAKHAND_LON_RANGE[1]):
            issue = DataIssue(
                snapshot_id=snapshot_id,
                entity="habitation",
                ref=f"hab_{hid}",
                issue_type="coordinates_out_of_district_bounds",
                status="open",
                details=f"Lat {lat}, Lon {lon} outside Uttarakhand bounds",
            )
            session.add(issue)
            issue_count += 1
            continue

        # Population Validation
        if pop <= 0 or pop > 50000:
            issue = DataIssue(
                snapshot_id=snapshot_id,
                entity="habitation",
                ref=f"hab_{hid}",
                issue_type="population_outlier",
                status="open",
                details=f"Population {pop} outside expected village range (1 to 50000)",
            )
            session.add(issue)
            issue_count += 1

        b_reg = block_map.get(hab_dict.get("block", ""), dist_region)
        existing_hab = session.get(Habitation, hid)
        if not existing_hab:
            hab = Habitation(
                id=hid,
                lgd_code=hab_dict.get("lgd_code"),
                name=hab_dict["name"],
                region_id=b_reg.id,
                lat=lat,
                lon=lon,
                elevation_m=hab_dict["elevation_m"],
                population=pop,
                pop_year=hab_dict.get("pop_year", 2011),
                sc_pct=sc,
                st_pct=st,
                loc_quality=hab_dict.get("loc_quality", "census_settlement_centroid"),
                snapshot_id=snapshot_id,
            )
            session.add(hab)
            hab_count += 1

    # 5. Ingest Facilities with Validation
    fac_count = 0
    for fac_dict in data.get("facilities", []):
        fid = fac_dict["id"]
        lat = fac_dict["lat"]
        lon = fac_dict["lon"]

        if not (UTTARAKHAND_LAT_RANGE[0] <= lat <= UTTARAKHAND_LAT_RANGE[1] and
                UTTARAKHAND_LON_RANGE[0] <= lon <= UTTARAKHAND_LON_RANGE[1]):
            issue = DataIssue(
                snapshot_id=snapshot_id,
                entity="facility",
                ref=f"fac_{fid}",
                issue_type="facility_coords_out_of_bounds",
                status="open",
                details=f"Lat {lat}, Lon {lon} outside Uttarakhand bounds",
            )
            session.add(issue)
            issue_count += 1
            continue

        b_reg = block_map.get(fac_dict.get("block", ""), dist_region)
        existing_fac = session.get(Facility, fid)
        if not existing_fac:
            fac = Facility(
                id=fid,
                name=fac_dict["name"],
                tier=fac_dict["tier"],
                lat=lat,
                lon=lon,
                elevation_m=fac_dict["elevation_m"],
                region_id=b_reg.id,
                is_functional=fac_dict.get("is_functional", True),
                doctor_count=fac_dict.get("doctor_count", 0),
                bed_count=fac_dict.get("bed_count", 0),
                snapshot_id=snapshot_id,
            )
            session.add(fac)
            fac_count += 1

    session.flush()

    return {
        "district": dist_name,
        "habitations_ingested": hab_count,
        "facilities_ingested": fac_count,
        "issues_logged": issue_count,
    }
