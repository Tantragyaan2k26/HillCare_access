"""Generate reproducible, clearly limited real-data diagnostics and outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GEOENGINE_SRC = PROJECT_ROOT / "packages" / "geoengine" / "src"
sys.path.insert(0, str(GEOENGINE_SRC))

from hillcare_geoengine.real_analysis import (  # noqa: E402
    derive_terrain_surfaces,
    district_review_records,
    nearest_facility_straight_line,
    road_geometry_diagnostics,
)
from hillcare_geoengine.real_data import DISTRICTS, RealDistrictData, load_real_district_data  # noqa: E402
from phase2a_raster_utils import read_geotiff_metadata, write_geotiff  # noqa: E402


DATA_DIR = PROJECT_ROOT / "data"
INVENTORY_PATH = DATA_DIR / "audit_phase1_20261020" / "source_hash_inventory.csv"
PHASE2A_REPORT_PATH = DATA_DIR / "processed_phase2a" / "phase2a_validation_report.json"
CODE_PATHS = (
    Path(__file__),
    PROJECT_ROOT / "scripts" / "phase2a_raster_utils.py",
    GEOENGINE_SRC / "hillcare_geoengine" / "real_analysis.py",
    GEOENGINE_SRC / "hillcare_geoengine" / "real_data.py",
)
CSV_FIELDS = (
    "habitation_source_id", "habitation_id", "habitation_name", "district",
    "metric", "units", "distance_m", "nearest_facility_source_id",
    "nearest_facility_id", "nearest_facility_name", "nearest_facility_tier",
    "facility_nic_source_id", "facility_pmgsy_source_id", "reachability",
    "habitation_properties_json", "facility_properties_json",
)
REVIEW_FIELDS = (
    "record_kind", "source_id", "district", "reason", "distance_to_district_m",
    "source_properties_json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, document: Any) -> None:
    path.write_text(
        json.dumps(_json_safe(document), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def verify_source_hash_inventory(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Require every inventoried original file to match its Phase 1 SHA-256."""
    if not INVENTORY_PATH.is_file():
        raise FileNotFoundError(f"Phase 1 source hash inventory is missing: {INVENTORY_PATH}")
    checked = 0
    failures: list[dict[str, str]] = []
    with INVENTORY_PATH.open(newline="", encoding="utf-8-sig") as source:
        for entry in csv.DictReader(source):
            relative_path = entry["relative_path"]
            path = project_root / Path(relative_path)
            expected = entry["active_sha256"].strip().lower()
            if not path.is_file():
                failures.append({"path": relative_path, "expected": expected, "actual": "missing"})
                continue
            actual = _sha256(path)
            checked += 1
            if actual != expected:
                failures.append({"path": relative_path, "expected": expected, "actual": actual})
    if failures:
        raise ValueError(f"Original source hash verification failed: {failures}")
    return {
        "inventory": str(INVENTORY_PATH.relative_to(project_root)),
        "files_checked": checked,
        "all_hashes_match": True,
        "inventory_sha256": _sha256(INVENTORY_PATH),
    }


def _write_results_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            converted = dict(row)
            converted["habitation_properties_json"] = json.dumps(
                _json_safe(converted.pop("habitation_properties")), sort_keys=True, allow_nan=False
            )
            converted["facility_properties_json"] = json.dumps(
                _json_safe(converted.pop("facility_properties")), sort_keys=True, allow_nan=False
            )
            writer.writerow(converted)


def _write_reviews_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for row in rows:
            converted = dict(row)
            converted["source_properties_json"] = json.dumps(
                _json_safe(converted.pop("source_properties")), sort_keys=True, allow_nan=False
            )
            writer.writerow(converted)


def _district_metadata(
    data: RealDistrictData,
    phase2a_validation: Mapping[str, Any],
) -> dict[str, Any]:
    dem = data.dem
    valid_pixels = int(np.count_nonzero(dem.valid_mask))
    total_pixels = int(dem.data.size)
    terrain = derive_terrain_surfaces(data)
    slope_valid_pixels = int(np.count_nonzero(terrain.valid_mask))
    rows = nearest_facility_straight_line(data.habitations, data.facilities)
    reviews = district_review_records(data)
    raster_validation = phase2a_validation["validation"][dem.path.name]
    return {
        "district": data.district,
        "counts": {
            "habitations": len(data.habitations),
            "facilities": len(data.facilities),
            "road_lines": len(data.roads),
            "boundary_features": 1,
            "habitations_with_straight_line_nearest_facility": sum(
                row["distance_m"] is not None for row in rows
            ),
        },
        "raster": {
            "path": str(dem.path.relative_to(DATA_DIR)),
            "crs": dem.crs.to_string(),
            "affine_transform": list(dem.transform),
            "pixel_size_m": list(dem.resolution),
            "shape_rows_cols": list(dem.data.shape),
            "nodata": dem.nodata,
            "valid_dem_pixels": valid_pixels,
            "nodata_dem_pixels": total_pixels - valid_pixels,
            "valid_dem_percent": (valid_pixels / total_pixels * 100.0) if total_pixels else 0.0,
            "slope_valid_pixels": slope_valid_pixels,
            "slope_nodata_pixels": total_pixels - slope_valid_pixels,
            "phase2a_district_boundary_violations": raster_validation["district_boundary_violations"],
            "phase2a_unsupported_source_valid_pixels_masked": raster_validation[
                "unsupported_source_valid_pixels_masked"
            ],
            "phase2a_valid_pixels_east_of_raw_coverage_edge": raster_validation.get(
                "valid_pixels_east_of_raw_coverage_edge"
            ),
        },
        "road_diagnostics": road_geometry_diagnostics(data.roads),
        "boundary_review_count": len(reviews),
        "boundary_review_records": reviews,
        "accessibility_metric": {
            "name": "nearest_facility_straight_line_distance",
            "units": "meters",
            "facility_set": "all source facility point records in the same district",
            "network_routing": False,
            "travel_time": False,
        },
        "_rows": rows,
        "_terrain": terrain,
    }


def _write_district_outputs(output_dir: Path, data: RealDistrictData, summary: dict[str, Any]) -> None:
    district_key = data.district.lower()
    rows = summary.pop("_rows")
    terrain = summary.pop("_terrain")
    _write_json(output_dir / f"real_{district_key}_results.json", summary | {"results": rows})
    _write_results_csv(output_dir / f"real_{district_key}_results.csv", rows)
    _write_reviews_csv(
        output_dir / f"real_{district_key}_boundary_reviews.csv",
        summary["boundary_review_records"],
    )
    metadata = read_geotiff_metadata(data.dem.path)
    raster_outputs = (
        (
            f"real_{district_key}_slope_degrees.tif",
            terrain.slope_degrees,
            "Terrain slope magnitude in degrees; central differences on valid cardinal neighbors.",
        ),
        (
            f"real_{district_key}_tobler_uphill_equivalent_speed_kmh.tif",
            terrain.uphill_equivalent_speed_kmh,
            "Isotropic uphill-equivalent Tobler speed proxy in km/h; not routed travel speed.",
        ),
        (
            f"real_{district_key}_tobler_uphill_equivalent_cost_min_per_km.tif",
            terrain.uphill_equivalent_minutes_per_km,
            "Isotropic uphill-equivalent Tobler proxy in min/km; not an origin-destination route cost.",
        ),
    )
    for filename, raster, description in raster_outputs:
        write_geotiff(
            output_dir / filename,
            raster,
            crs_epsg=data.dem.crs.to_epsg(),
            transform=metadata.transform,
            nodata=data.dem.nodata,
            description=description,
        )


def _render_report(document: Mapping[str, Any]) -> str:
    lines = [
        "# Real-data geographic access diagnostics",
        "",
        "This run is a real-data diagnostic, separate from the synthetic/demo pipeline.",
        "It does not calculate routed access, actual travel time, unmet need, or facility service availability.",
        "",
        "## Inputs and method",
        "",
        f"- Original input hash verification: {document['source_hash_verification']['files_checked']} files checked; "
        f"all match the Phase 1 inventory.",
        "- Habitations and facilities are matched only by nearest straight-line distance in the district DEM's projected CRS.",
        "- Distance is in meters; it is not road distance, walking distance, or travel time.",
        "- The terrain Tobler layers are local isotropic uphill-equivalent proxies and are not used to calculate the distance results.",
        "- WorldPop density is not converted into habitation population counts and is not used in these metrics.",
        "- No road graph is built: 2D intersections do not resolve grade separation or bridge/junction semantics.",
        "- Road speed attributes are reported as source-data summaries only; their provenance is not verified and they are not used as travel-time inputs.",
        "- Facility functionality, capacity, opening status, and service availability are not inferred.",
        "",
        "## District results",
        "",
    ]
    for district in document["districts"]:
        raster = district["raster"]
        roads = district["road_diagnostics"]
        lines.extend([
            f"### {district['district']}",
            "",
            f"- Source records: {district['counts']['habitations']} habitations, "
            f"{district['counts']['facilities']} facilities, {district['counts']['road_lines']} road LineStrings.",
            f"- DEM: {raster['crs']}, {raster['pixel_size_m'][0]:g} x {raster['pixel_size_m'][1]:g} m, "
            f"{raster['shape_rows_cols'][0]} x {raster['shape_rows_cols'][1]} pixels.",
            f"- Valid DEM coverage: {raster['valid_dem_pixels']:,}/{raster['shape_rows_cols'][0] * raster['shape_rows_cols'][1]:,} "
            f"pixels ({raster['valid_dem_percent']:.2f}%); slope derivative valid pixels: {raster['slope_valid_pixels']:,}.",
            f"- Phase 2A boundary-coverage violations: {raster['phase2a_district_boundary_violations']}; "
            f"unsupported source cells masked: {raster['phase2a_unsupported_source_valid_pixels_masked']}.",
            f"- Boundary/geometry review records retained: {district['boundary_review_count']}.",
            f"- Road checks: {roads['valid_line_geometry_count']} valid line geometries; "
            f"{roads['duplicate_er_id_extra_rows']} extra rows with duplicate road IDs; "
            f"{roads['geometrically_intersecting_segment_pairs']} 2D intersecting pairs; "
            f"{roads['provisional_components_by_2d_intersection']} provisional geometric components.",
            "- These geometric components are diagnostics only, not validated route-network components.",
            "",
        ])
    lines.extend([
        "## Limitations",
        "",
        "The nearest-facility result is a geographic proximity measure. It does not account for terrain barriers, "
        "roads, rivers, bridges, facility tier preferences, or service availability. Every source habitation and "
        "facility record remains represented by its preserved source identifiers and properties; records requiring "
        "review are listed in district-specific review CSVs.",
        "",
        "The Tobler proxy applies the magnitude of local DEM slope as an uphill-equivalent gradient. It is not "
        "directional, does not identify a path, and is not reported as an accessibility travel time.",
        "",
    ])
    return "\n".join(lines)


def run_analysis(data_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    hash_status = verify_source_hash_inventory()
    phase2a_validation = json.loads(PHASE2A_REPORT_PATH.read_text(encoding="utf-8"))
    code_hashes = {
        str(path.relative_to(PROJECT_ROOT)): _sha256(path)
        for path in CODE_PATHS
    }
    code_sha = hashlib.sha256(
        json.dumps(code_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    districts: list[dict[str, Any]] = []
    for name in DISTRICTS:
        loaded = load_real_district_data(data_dir, name)
        summary = _district_metadata(loaded, phase2a_validation)
        _write_district_outputs(output_dir, loaded, summary)
        districts.append(summary)

    total_counts = {
        key: sum(district["counts"][key] for district in districts)
        for key in ("habitations", "facilities", "road_lines")
    }
    document = {
        "schema_version": "1.0.0",
        "analysis_mode": "real_data_geographic_access_diagnostics",
        "result_type": "straight_line_proximity_and_terrain_diagnostics",
        "synthetic": False,
        "code_sha256": code_sha,
        "code_file_sha256": code_hashes,
        "source_hash_verification": hash_status,
        "phase2a_validation_report": str(PHASE2A_REPORT_PATH.relative_to(PROJECT_ROOT)),
        "phase2a_validation_sha256": _sha256(PHASE2A_REPORT_PATH),
        "source_counts": total_counts,
        "worldpop_used_as_habitation_population": False,
        "road_network_routing_implemented": False,
        "actual_travel_times_produced": False,
        "unreachable_habitations_classified": False,
        "districts": districts,
    }
    _write_json(output_dir / "real_analysis_report.json", document)
    (output_dir / "real_analysis_report.md").write_text(_render_report(document), encoding="utf-8")
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_DIR / "analysis_real_20261020",
        help="New output directory; non-empty directories are never overwritten.",
    )
    args = parser.parse_args()
    result = run_analysis(args.data_dir.resolve(), args.output_dir)
    print(json.dumps({
        "analysis_mode": result["analysis_mode"],
        "source_counts": result["source_counts"],
        "output_dir": str(args.output_dir.resolve()),
        "source_hash_verification": result["source_hash_verification"],
    }, indent=2))


if __name__ == "__main__":
    main()
