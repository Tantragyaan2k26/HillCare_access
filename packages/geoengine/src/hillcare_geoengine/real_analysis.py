"""Defensible real-data diagnostics and non-network accessibility measures."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.spatial import cKDTree
from shapely.strtree import STRtree

from hillcare_geoengine.real_data import RealDistrictData, RealFeature


@dataclass(frozen=True)
class TerrainSurfaces:
    """Terrain derivatives; the speed/cost layers are an isotropic proxy."""

    slope_degrees: np.ndarray
    uphill_equivalent_speed_kmh: np.ndarray
    uphill_equivalent_minutes_per_km: np.ndarray
    valid_mask: np.ndarray
    nodata: float


def derive_terrain_surfaces(data: RealDistrictData) -> TerrainSurfaces:
    """Derive central-difference slope and a declared Tobler terrain proxy.

    The slope is the magnitude of the DEM gradient. It is treated as
    uphill-equivalent when evaluated with Tobler's function; this is an
    intentionally conservative, direction-independent terrain proxy, not a
    directional route cost or a travel-time surface between locations.
    Cells lacking a valid center or cardinal neighbor remain nodata.
    """
    dem = data.dem.data
    source_valid = data.dem.valid_mask
    if dem.ndim != 2 or source_valid.shape != dem.shape:
        raise ValueError("DEM and valid-data mask must be aligned two-dimensional arrays.")
    if data.dem.resolution[0] <= 0 or data.dem.resolution[1] <= 0:
        raise ValueError("DEM resolution must be positive.")

    rows, cols = dem.shape
    nodata = data.dem.nodata
    slope = np.full(dem.shape, nodata, dtype=np.float32)
    center = source_valid[1:-1, 1:-1]
    west = source_valid[1:-1, :-2]
    east = source_valid[1:-1, 2:]
    north = source_valid[:-2, 1:-1]
    south = source_valid[2:, 1:-1]
    valid = center & west & east & north & south
    dx = data.dem.resolution[0]
    dy = data.dem.resolution[1]

    dz_dx = (dem[1:-1, 2:] - dem[1:-1, :-2]) / (2.0 * dx)
    dz_dy = (dem[2:, 1:-1] - dem[:-2, 1:-1]) / (2.0 * dy)
    gradient = np.hypot(dz_dx, dz_dy)
    slope_inner = slope[1:-1, 1:-1]
    slope_inner[valid] = np.degrees(np.arctan(gradient[valid])).astype(np.float32)

    speed = np.full(dem.shape, nodata, dtype=np.float32)
    valid_slope = slope != nodata
    slope_rise_run = np.tan(np.radians(slope[valid_slope])).astype(np.float32)
    speed[valid_slope] = (
        6.0 * np.exp(-3.5 * np.abs(slope_rise_run + 0.05))
    ).astype(np.float32)
    minutes_per_km = np.full(dem.shape, nodata, dtype=np.float32)
    minutes_per_km[valid_slope] = 60.0 / speed[valid_slope]
    return TerrainSurfaces(
        slope_degrees=slope,
        uphill_equivalent_speed_kmh=speed,
        uphill_equivalent_minutes_per_km=minutes_per_km,
        valid_mask=valid_slope,
        nodata=nodata,
    )


def nearest_facility_straight_line(
    habitations: Sequence[RealFeature],
    facilities: Sequence[RealFeature],
) -> list[dict[str, Any]]:
    """Return nearest facility by projected Euclidean distance, not routing."""
    eligible = [
        feature for feature in facilities
        if feature.projected_geometry is not None and feature.projected_geometry.geom_type == "Point"
    ]
    facility_coordinates = []
    for feature in eligible:
        geometry = feature.projected_geometry
        assert geometry is not None
        facility_coordinates.append((geometry.x, geometry.y))
    tree = cKDTree(facility_coordinates) if facility_coordinates else None

    results: list[dict[str, Any]] = []
    for habitation in habitations:
        point = habitation.projected_geometry
        if point is None or point.geom_type != "Point":
            index = None
            distance = None
            facility = None
            reachability = "invalid_habitation_geometry"
        elif tree is None:
            index = None
            distance = None
            facility = None
            reachability = "no_facilities"
        else:
            distance, index = tree.query((point.x, point.y), k=1)
            facility = eligible[int(index)]
            distance = float(distance)
            reachability = "straight_line_nearest_only"
        results.append({
            "habitation_source_id": habitation.source_id,
            "habitation_id": habitation.properties.get("id"),
            "habitation_name": habitation.properties.get("name"),
            "district": habitation.district,
            "habitation_properties": dict(habitation.properties),
            "metric": "nearest_facility_straight_line_distance",
            "units": "meters",
            "distance_m": distance,
            "nearest_facility_source_id": facility.source_id if facility else None,
            "nearest_facility_id": facility.properties.get("facility_id") if facility else None,
            "nearest_facility_name": facility.properties.get("name") if facility else None,
            "nearest_facility_tier": facility.properties.get("tier") if facility else None,
            "facility_nic_source_id": facility.properties.get("nic_source_id") if facility else None,
            "facility_pmgsy_source_id": facility.properties.get("pmgsy_source_id") if facility else None,
            "facility_properties": dict(facility.properties) if facility else None,
            "reachability": reachability,
        })
    return results


def road_geometry_diagnostics(roads: Sequence[RealFeature]) -> dict[str, Any]:
    """Inspect geometry intersections without asserting routable connectivity."""
    geometries = [road.projected_geometry for road in roads]
    invalid = [
        road for road in roads
        if road.projected_geometry is None
        or road.projected_geometry.is_empty
        or not road.projected_geometry.is_valid
        or road.projected_geometry.geom_type not in ("LineString", "MultiLineString")
    ]
    usable = [
        (index, geometry)
        for index, geometry in enumerate(geometries)
        if geometry is not None and not geometry.is_empty and geometry.is_valid
        and geometry.geom_type in ("LineString", "MultiLineString")
    ]

    parent = list(range(len(roads)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    intersection_pairs = 0
    if usable:
        tree = STRtree([geometry for _, geometry in usable])
        for tree_index, (_, geometry) in enumerate(usable):
            for candidate in tree.query(geometry):
                other_index = int(candidate)
                if other_index <= tree_index:
                    continue
                if geometry.intersects(usable[other_index][1]):
                    intersection_pairs += 1
                    union(usable[tree_index][0], usable[other_index][0])

    component_sizes = Counter(find(index) for index, _ in usable)
    source_ids = [road.properties.get("er_id") for road in roads]
    id_counts = Counter(source_id for source_id in source_ids if source_id is not None)
    duplicate_id_rows = sum(count - 1 for count in id_counts.values() if count > 1)
    missing_ids = sum(source_id is None for source_id in source_ids)
    duplicate_ids = [
        {"er_id": source_id, "row_count": count}
        for source_id, count in sorted(id_counts.items(), key=lambda item: str(item[0]))
        if count > 1
    ]
    road_type_counts = Counter(str(road.properties.get("road_type")) for road in roads)
    motorable_counts = Counter(str(road.properties.get("is_motorable")) for road in roads)
    speed_counts = Counter(str(road.properties.get("speed_kmh")) for road in roads)

    return {
        "segment_count": len(roads),
        "valid_line_geometry_count": len(usable),
        "invalid_or_unsupported_geometry_count": len(invalid),
        "invalid_or_unsupported_source_ids": [road.source_id for road in invalid],
        "missing_source_id_count": missing_ids,
        "missing_source_id_rows": [
            index for index, source_id in enumerate(source_ids) if source_id is None
        ],
        "duplicate_er_id_extra_rows": duplicate_id_rows,
        "duplicate_er_ids": duplicate_ids,
        "road_type_counts": dict(sorted(road_type_counts.items())),
        "is_motorable_value_counts": dict(sorted(motorable_counts.items())),
        "speed_kmh_value_counts": dict(sorted(speed_counts.items())),
        "geometrically_intersecting_segment_pairs": intersection_pairs,
        "provisional_components_by_2d_intersection": len(component_sizes),
        "provisional_largest_component_segments": max(component_sizes.values(), default=0),
        "provisional_singleton_segments": sum(size == 1 for size in component_sizes.values()),
        "connectivity_interpretation": (
            "Provisional 2D geometric intersections only; not a routing graph. "
            "Grade separation, bridge status, and connection tolerance are not verified."
        ),
        "routing_graph_implemented": False,
    }


def district_review_records(data: RealDistrictData) -> list[dict[str, Any]]:
    """Serialize invalid or out-of-boundary source records without dropping them."""
    records: list[dict[str, Any]] = []
    for collection in (data.habitations, data.facilities, data.roads):
        for feature in collection:
            reason = "; ".join(feature.issues)
            distance: float | None = None
            if feature.projected_geometry is None:
                reason = reason or "geometry could not be projected"
            elif data.boundary.projected_geometry is None:
                reason = reason or "district boundary could not be projected"
            elif not data.boundary.projected_geometry.covers(feature.projected_geometry):
                boundary = data.boundary.projected_geometry
                distance = float(boundary.distance(feature.projected_geometry))
                kind_note = "point" if feature.projected_geometry.geom_type == "Point" else "geometry"
                outside_reason = f"{kind_note} extends outside its assigned district polygon"
                reason = f"{reason}; {outside_reason}" if reason else outside_reason
            if reason:
                records.append({
                    "record_kind": feature.kind,
                    "source_id": feature.source_id,
                    "district": feature.district,
                    "reason": reason,
                    "distance_to_district_m": distance,
                    "source_properties": dict(feature.properties),
                })
    return records
