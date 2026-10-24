"""Tests for explicit, read-only real-data loading."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import tifffile
from hillcare_geoengine.real_analysis import (
    derive_terrain_surfaces,
    district_review_records,
    nearest_facility_straight_line,
    road_geometry_diagnostics,
)
from hillcare_geoengine.real_data import load_real_district_data
from pyproj import Transformer
from shapely.geometry import LineString, Point, box
from shapely.ops import transform

CRS84 = {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}
DISTRICT = "Chamoli"


def _feature(geometry: dict[str, Any], properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def _collection(features: list[dict[str, Any]], crs: dict[str, Any] = CRS84) -> dict[str, Any]:
    return {"type": "FeatureCollection", "crs": crs, "features": features}


def _write_fixture_dem(path: Path, data: np.ndarray, transform: tuple[float, ...]) -> None:
    keys = (1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, 32644)
    tifffile.imwrite(
        path,
        data,
        photometric="minisblack",
        metadata=None,
        extratags=[
            (33550, "d", 3, (transform[0], abs(transform[4]), 0.0), False),
            (33922, "d", 6, (0.0, 0.0, 0.0, transform[2], transform[5], 0.0), False),
            (34735, "H", len(keys), keys, False),
            (42113, "s", 0, "-9999\x00", False),
        ],
    )


@pytest.fixture
def real_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    processed = data_dir / "processed"
    derived = data_dir / "processed_phase2a"
    processed.mkdir(parents=True)
    derived.mkdir()

    boundary = box(79.0, 29.9, 79.1, 30.0)
    boundaries = []
    for district, geom, code in (
        (DISTRICT, boundary, 1),
        ("Pithoragarh", box(80.0, 29.9, 80.1, 30.0), 2),
        ("Rudraprayag", box(78.9, 30.0, 79.0, 30.1), 3),
    ):
        boundaries.append(
            _feature(
                {"type": "Polygon", "coordinates": [list(geom.exterior.coords)]},
                {"district_name": district, "lgd_code": code},
            )
        )
    (processed / "district_boundaries.geojson").write_text(
        json.dumps(_collection(boundaries)), encoding="utf-8"
    )

    habitations = [
        _feature({"type": "Point", "coordinates": [79.02, 29.95]},
                 {"id": 101, "name": "Inside", "district": DISTRICT, "population": 12, "source": "test"}),
        _feature({"type": "Point", "coordinates": [79.2, 29.95]},
                 {"id": 102, "name": "Outside", "district": DISTRICT, "population": 34, "source": "test"}),
        _feature({"type": "Point", "coordinates": [999.0, 29.95]},
                 {"id": 103, "name": "Invalid CRS coordinate", "district": DISTRICT, "source": "test"}),
    ]
    (processed / "habitations_target_districts.geojson").write_text(
        json.dumps(_collection(habitations)), encoding="utf-8"
    )
    facilities = [
        _feature({"type": "Point", "coordinates": [79.03, 29.96]},
                 {"id": 201, "facility_id": "NIC_201", "nic_source_id": "201",
                  "tier": "PHC", "district": DISTRICT, "source": "NIC"}),
        _feature({"type": "Point", "coordinates": [79.04, 29.97]},
                 {"id": 202, "facility_id": "PMGSY_202", "pmgsy_source_id": "202",
                  "tier": "HWC", "district": DISTRICT, "source": "PMGSY"}),
    ]
    (processed / "facilities_target_districts.geojson").write_text(
        json.dumps(_collection(facilities)), encoding="utf-8"
    )
    roads = [
        _feature({"type": "LineString", "coordinates": [[79.01, 29.91], [79.08, 29.99]]},
                 {"er_id": "road-A", "district": DISTRICT, "source": "PMGSY",
                  "is_motorable": False}),
    ]
    (processed / "roads_target_districts.geojson").write_text(
        json.dumps(_collection(roads)), encoding="utf-8"
    )

    transformer = Transformer.from_crs(4326, 32644, always_xy=True)
    projected = transform(transformer.transform, boundary)
    x0, y0, x1, y1 = projected.bounds
    x0 = np.floor(x0 / 30) * 30
    y1 = np.ceil(y1 / 30) * 30
    rows = int(np.ceil((y1 - y0) / 30))
    cols = int(np.ceil((x1 - x0) / 30))
    array = np.full((rows, cols), 100.0, dtype=np.float32)
    array[0, 0] = -9999.0
    raster_path = derived / "dem_chamoli_utm44n.tif"
    affine = (30.0, 0.0, x0, 0.0, -30.0, y1)
    _write_fixture_dem(
        raster_path,
        array,
        affine,
    )
    sidecar = {
        "district": DISTRICT,
        "crs": "EPSG:32644",
        "transform": affine,
        "shape": array.shape,
        "nodata": -9999.0,
    }
    (processed / "dem_chamoli_utm44n.json").write_text(json.dumps(sidecar), encoding="utf-8")
    return data_dir


def test_loads_raster_metadata_mask_and_source_vector_counts(real_data_dir: Path):
    loaded = load_real_district_data(real_data_dir, DISTRICT)

    assert loaded.dem.crs.to_epsg() == 32644
    assert loaded.dem.resolution == (30.0, 30.0)
    assert loaded.dem.nodata == -9999.0
    assert loaded.dem.data.dtype == np.float32
    assert loaded.dem.valid_mask.shape == loaded.dem.data.shape
    assert not loaded.dem.valid_mask[0, 0]
    assert loaded.dem.valid_mask[1, 1]
    assert len(loaded.habitations) == 3
    assert len(loaded.facilities) == 2
    assert len(loaded.roads) == 1
    assert loaded.facilities[0].source_id == "201"
    assert loaded.facilities[0].properties["nic_source_id"] == "201"
    assert loaded.facilities[1].source_id == "202"
    assert loaded.roads[0].source_id == "road-A"
    assert loaded.roads[0].properties["is_motorable"] is False
    assert loaded.habitations[0].properties["population"] == 12
    assert not hasattr(loaded, "worldpop")
    assert loaded.habitations[0].source_crs.to_authority() == ("OGC", "CRS84")
    assert loaded.habitations[0].projected_crs.to_epsg() == 32644
    assert loaded.habitations[0].projected_geometry is not None
    assert loaded.habitations[0].projected_geometry.x != loaded.habitations[0].source_geometry.x


def test_outside_and_invalid_habitations_remain_in_review(real_data_dir: Path):
    loaded = load_real_district_data(real_data_dir, DISTRICT)

    reviews = {entry.source_id: entry for entry in loaded.review_records}
    assert set(reviews) == {102, 103}
    assert "outside its assigned district polygon" in reviews[102].reason
    assert reviews[102].distance_to_district_m is not None
    assert reviews[reviews[102].source_id].feature in loaded.habitations
    assert "outside declared geographic CRS bounds" in reviews[103].reason
    assert reviews[103].distance_to_district_m is None


def test_rejects_vector_without_verified_crs_declaration(real_data_dir: Path):
    path = real_data_dir / "processed" / "facilities_target_districts.geojson"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["crs"] = {"type": "name", "properties": {"name": "EPSG:3857"}}
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="CRS84/EPSG:4326"):
        load_real_district_data(real_data_dir, DISTRICT)


def test_rejects_raster_metadata_disagreeing_with_sidecar(real_data_dir: Path):
    path = real_data_dir / "processed" / "dem_chamoli_utm44n.json"
    sidecar = json.loads(path.read_text(encoding="utf-8"))
    sidecar["crs"] = "EPSG:4326"
    path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(ValueError, match="embedded CRS disagrees"):
        load_real_district_data(real_data_dir, DISTRICT)


def test_rejects_unknown_district(real_data_dir: Path):
    with pytest.raises(ValueError, match="Unknown pilot district"):
        load_real_district_data(real_data_dir, "Unknown")


def test_terrain_slope_and_tobler_proxy_use_projected_pixel_resolution(real_data_dir: Path):
    loaded = load_real_district_data(real_data_dir, DISTRICT)
    elevations = np.tile(np.arange(5, dtype=np.float32) * 30.0, (5, 1))
    raster = replace(
        loaded.dem,
        data=elevations,
        valid_mask=np.ones(elevations.shape, dtype=bool),
        resolution=(30.0, 30.0),
    )
    surfaces = derive_terrain_surfaces(replace(loaded, dem=raster))

    assert surfaces.slope_degrees[2, 2] == pytest.approx(45.0, abs=1e-5)
    expected_speed = 6.0 * np.exp(-3.5 * abs(1.0 + 0.05))
    assert surfaces.uphill_equivalent_speed_kmh[2, 2] == pytest.approx(expected_speed, rel=1e-6)
    assert surfaces.uphill_equivalent_minutes_per_km[2, 2] == pytest.approx(60.0 / expected_speed)
    assert surfaces.valid_mask[2, 2]
    assert not surfaces.valid_mask[0, 0]


def test_terrain_derivatives_propagate_nodata_neighbors(real_data_dir: Path):
    loaded = load_real_district_data(real_data_dir, DISTRICT)
    elevations = np.full((5, 5), 100.0, dtype=np.float32)
    valid = np.ones(elevations.shape, dtype=bool)
    elevations[2, 2] = -9999.0
    valid[2, 2] = False
    surfaces = derive_terrain_surfaces(replace(
        loaded,
        dem=replace(loaded.dem, data=elevations, valid_mask=valid),
    ))

    assert not surfaces.valid_mask[2, 2]
    assert not surfaces.valid_mask[1, 2]
    assert not surfaces.valid_mask[2, 1]
    assert surfaces.slope_degrees[2, 2] == -9999.0
    assert np.all(surfaces.uphill_equivalent_minutes_per_km[~surfaces.valid_mask] == -9999.0)


def test_nearest_facility_metric_is_projected_distance_and_preserves_ids(real_data_dir: Path):
    loaded = load_real_district_data(real_data_dir, DISTRICT)
    habitation = replace(
        loaded.habitations[0],
        source_id=9101,
        projected_geometry=Point(loaded.facilities[0].projected_geometry.x + 30.0,
                                 loaded.facilities[0].projected_geometry.y),
    )
    result = nearest_facility_straight_line((habitation,), loaded.facilities)[0]

    assert result["habitation_source_id"] == 9101
    assert result["nearest_facility_source_id"] == "201"
    assert result["facility_nic_source_id"] == "201"
    assert result["distance_m"] == pytest.approx(30.0)
    assert result["units"] == "meters"
    assert result["reachability"] == "straight_line_nearest_only"


def test_road_intersections_are_reported_as_provisional_not_routing(real_data_dir: Path):
    loaded = load_real_district_data(real_data_dir, DISTRICT)
    roads = (
        replace(loaded.roads[0], projected_geometry=LineString([(0, 0), (10, 10)])),
        replace(loaded.roads[0], properties={"er_id": "road-B"},
                projected_geometry=LineString([(0, 10), (10, 0)])),
        replace(loaded.roads[0], properties={"er_id": "road-A"},
                projected_geometry=LineString([(100, 100), (110, 110)])),
    )
    diagnostics = road_geometry_diagnostics(roads)

    assert diagnostics["segment_count"] == 3
    assert diagnostics["geometrically_intersecting_segment_pairs"] == 1
    assert diagnostics["provisional_components_by_2d_intersection"] == 2
    assert diagnostics["duplicate_er_ids"] == [{"er_id": "road-A", "row_count": 2}]
    assert diagnostics["road_type_counts"]["None"] == 3
    assert diagnostics["routing_graph_implemented"] is False
    assert "not a routing graph" in diagnostics["connectivity_interpretation"]


def test_review_output_keeps_outside_and_invalid_source_records(real_data_dir: Path):
    loaded = load_real_district_data(real_data_dir, DISTRICT)
    reviews = district_review_records(loaded)

    assert {record["source_id"] for record in reviews if record["record_kind"] == "habitation"} == {102, 103}
    assert next(record for record in reviews if record["source_id"] == 102)["distance_to_district_m"] > 0
