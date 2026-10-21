"""Read-only endpoints for the locally processed real district datasets."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/real-data", tags=["Real district data"])
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = PROJECT_ROOT / "data"
DISTRICTS = ("Chamoli", "Pithoragarh", "Rudraprayag")
EARTH_MEAN_RADIUS_KM = 6371.0088
ROAD_FEATURE_COUNTS = {"Chamoli": 954, "Pithoragarh": 897, "Rudraprayag": 458}
ROAD_SOURCE_SHA256 = "aec6c37be6ea89c1dfb57b1db32d3d3d109906fabde031d827e879bd59a9a799"


@lru_cache(maxsize=1)
def _verify_road_source_snapshot() -> None:
    path = DATA_DIR / "processed" / "roads_target_districts.geojson"
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != ROAD_SOURCE_SHA256:
        raise ValueError(
            f"{path} differs from the audited road snapshot; review the source hash and district counts."
        )


def _feature_id(feature: dict[str, Any], layer: str) -> str | int | None:
    properties = feature.get("properties") or {}
    for name in {
        "habitations": ("id",),
        "facilities": ("nic_source_id", "pmgsy_source_id", "facility_id", "id"),
        "roads": ("er_id",),
        "boundaries": ("lgd_code",),
    }[layer]:
        value = properties.get(name)
        if value is not None and value != "":
            return value
    return None


def _outside_boundary_counts() -> dict[str, int]:
    path = DATA_DIR / "audit_phase1_20261020" / "habitation_district_outliers.csv"
    counts = {district: 0 for district in DISTRICTS}
    if not path.is_file():
        return counts
    with path.open(newline="", encoding="utf-8-sig") as source:
        for record in csv.DictReader(source):
            if record.get("assigned_district") in counts:
                counts[record["assigned_district"]] += 1
    return counts


def _outside_boundary_ids() -> dict[str, set[str]]:
    path = DATA_DIR / "audit_phase1_20261020" / "habitation_district_outliers.csv"
    records = {district: set() for district in DISTRICTS}
    if not path.is_file():
        return records
    with path.open(newline="", encoding="utf-8-sig") as source:
        for record in csv.DictReader(source):
            district = record.get("assigned_district")
            habitation_id = record.get("habitation_id")
            if district in records and habitation_id:
                records[district].add(str(habitation_id))
    return records


def _great_circle_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    value = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_MEAN_RADIUS_KM * math.asin(math.sqrt(min(1.0, value)))


@lru_cache(maxsize=4)
def _load_layer(filename: str) -> dict[str, Any]:
    path = DATA_DIR / "processed" / filename
    document = json.loads(path.read_text(encoding="utf-8"))
    crs = (document.get("crs") or {}).get("properties", {}).get("name")
    if crs != "urn:ogc:def:crs:OGC:1.3:CRS84":
        raise ValueError(f"{path} does not declare the verified project CRS84 coordinates.")
    if document.get("type") != "FeatureCollection":
        raise ValueError(f"{path} is not a GeoJSON FeatureCollection.")
    return document


@lru_cache(maxsize=12)
def _district_features(layer: str, district: str) -> tuple[dict[str, Any], ...]:
    filename = {
        "habitations": "habitations_target_districts.geojson",
        "facilities": "facilities_target_districts.geojson",
        "roads": "roads_target_districts.geojson",
        "boundaries": "district_boundaries.geojson",
    }[layer]
    features = _load_layer(filename)["features"]
    return tuple(
        feature for feature in features
        if (feature.get("properties") or {}).get("district") == district
        or (
            layer == "boundaries"
            and (feature.get("properties") or {}).get("district_name") == district
        )
    )


def _nearest_facilities(habitations: list[dict[str, Any]], facilities: list[dict[str, Any]]) -> None:
    facility_points: list[tuple[dict[str, Any], float, float]] = []
    for feature in facilities:
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") == "Point" and len(coordinates) >= 2:
            facility_points.append((feature, float(coordinates[0]), float(coordinates[1])))

    for habitation in habitations:
        geometry = habitation.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") != "Point" or len(coordinates) < 2 or not facility_points:
            habitation["nearest_facility"] = None
            continue
        lon, lat = float(coordinates[0]), float(coordinates[1])
        nearest, distance = min(
            (
                (facility, _great_circle_km(lon, lat, fac_lon, fac_lat))
                for facility, fac_lon, fac_lat in facility_points
            ),
            key=lambda item: item[1],
        )
        nearest_properties = nearest.get("properties") or {}
        habitation["nearest_facility"] = {
            "source_id": _feature_id(nearest, "facilities"),
            "facility_id": nearest_properties.get("facility_id"),
            "name": nearest_properties.get("name"),
            "tier": nearest_properties.get("tier"),
            "distance_km": round(distance, 3),
            "distance_method": "WGS84-coordinate spherical great-circle (mean Earth radius 6371.0088 km)",
        }


@lru_cache(maxsize=3)
def load_real_district(district: str) -> dict[str, Any]:
    """Load and verify the source CRS before returning a district feature bundle."""
    if district not in DISTRICTS:
        raise ValueError(f"Unsupported district: {district}")
    _verify_road_source_snapshot()
    layers = {
        layer: list(_district_features(layer, district))
        for layer in ("habitations", "facilities", "boundaries")
    }

    if len(layers["boundaries"]) != 1:
        raise ValueError(f"Expected exactly one district boundary for {district}.")
    _nearest_facilities(layers["habitations"], layers["facilities"])
    outlier_ids = _outside_boundary_ids()[district]
    for feature in layers["habitations"]:
        properties = feature.get("properties") or {}
        if str(properties.get("id")) in outlier_ids:
            feature["review_flags"] = ["outside assigned district boundary; source assignment retained for review"]
    counts = {
        "habitations": len(layers["habitations"]),
        "facilities": len(layers["facilities"]),
        "road_segments": ROAD_FEATURE_COUNTS[district],
        "district_boundaries": len(layers["boundaries"]),
        "habitations_outside_assigned_boundary": _outside_boundary_counts()[district],
    }
    return {
        "analysis_mode": "real_data_map",
        "district": district,
        "crs": "OGC:CRS84 longitude,latitude (equivalent coordinate values to EPSG:4326)",
        "counts": counts,
        "methodology": {
            "source_attribution": "Publisher-level attribution is not independently verified per record.",
            "habitation_population": "Source feature attribute; not used in nearest-facility distance.",
            "nearest_facility": "Spherical great-circle proximity from source coordinates; not road distance or travel time.",
            "road_routing": False,
            "worldpop_population_assignment": False,
        },
        "layers": {
            "boundaries": layers["boundaries"],
            "habitations": layers["habitations"],
            "facilities": layers["facilities"],
            "roads": [],
        },
        "provenance": {
            "habitations": "PMGSY GeoSadak (manifest attribution; underlying mirror lineage unverified)",
            "facilities": "NIC/PMGSY (manifest attribution; individual source IDs and lineage vary)",
            "roads": "PMGSY GeoSadak DRRP (manifest attribution; underlying mirror lineage unverified)",
            "boundaries": "Local Government Directory / Survey of India (manifest attribution; source file lineage unverified)",
            "record_verification_status": "source attribution not independently verified per feature",
        },
    }


@router.get("/districts")
def list_real_districts():
    return [{"name": district, "analysis_mode": "real_data_map"} for district in DISTRICTS]


@router.get("/districts/{district}")
def get_real_district(district: str, include_roads: bool = Query(default=True)):
    if district not in DISTRICTS:
        raise HTTPException(status_code=404, detail=f"Unsupported district: {district}")
    try:
        data = load_real_district(district)
        if not include_roads:
            return data
        roads = _district_features("roads", district)
        if len(roads) != ROAD_FEATURE_COUNTS[district]:
            raise ValueError(
                f"Expected {ROAD_FEATURE_COUNTS[district]} road features for {district}, found {len(roads)}."
            )
        return {**data, "layers": {**data["layers"], "roads": list(roads)}}
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Unable to load verified real-data inputs: {exc}") from exc


@router.get("/districts/{district}/roads")
def get_real_district_roads(district: str):
    if district not in DISTRICTS:
        raise HTTPException(status_code=404, detail=f"Unsupported district: {district}")
    try:
        _verify_road_source_snapshot()
        features = _district_features("roads", district)
        if len(features) != ROAD_FEATURE_COUNTS[district]:
            raise ValueError(
                f"Expected {ROAD_FEATURE_COUNTS[district]} road features for {district}, found {len(features)}."
            )
        return {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "district": district,
            "count": len(features),
            "features": features,
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Unable to load verified road geometries: {exc}") from exc
