"""Create a read-only provenance and data-issue audit in a new directory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any
import zipfile

import tifffile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT = DATA_DIR / "provenance_audit_20261020_final"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raster_facts(path: Path) -> dict[str, Any]:
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        tags = page.tags
        geokeys = tags["GeoKeyDirectoryTag"].value if "GeoKeyDirectoryTag" in tags else ()
        epsg_key = None
        raster_type = None
        for offset in range(4, len(geokeys), 4):
            key, _, _, value = geokeys[offset:offset + 4]
            if key in (2048, 3072):
                epsg_key = value
            if key == 1025:
                raster_type = value
        scale = tags["ModelPixelScaleTag"].value if "ModelPixelScaleTag" in tags else None
        tiepoint = tags["ModelTiepointTag"].value if "ModelTiepointTag" in tags else None
        nodata = tags["GDAL_NODATA"].value if "GDAL_NODATA" in tags else None
        derived_georeferencing = None
        if scale and tiepoint and len(scale) >= 2 and len(tiepoint) >= 6:
            sx, sy = float(scale[0]), float(scale[1])
            i, j, _, tie_x, tie_y, _ = (float(value) for value in tiepoint[:6])
            origin_x = tie_x - i * sx
            origin_y = tie_y + j * sy
            if raster_type == 2:
                origin_x -= sx / 2
                origin_y += sy / 2
            rows, cols = page.shape[-2:]
            derived_georeferencing = {
                "affine_origin": [origin_x, origin_y],
                "pixel_size": [sx, sy],
                "outer_bounds": [
                    origin_x,
                    origin_y - rows * sy,
                    origin_x + cols * sx,
                    origin_y,
                ],
            }
        return {
            "dimensions_rows_cols": list(page.shape),
            "dtype": str(page.dtype),
            "embedded_epsg_key": epsg_key,
            "geotiff_raster_type": {1: "PixelIsArea", 2: "PixelIsPoint"}.get(raster_type, raster_type),
            "pixel_scale_tag": list(scale) if scale is not None else None,
            "tiepoint_tag": list(tiepoint) if tiepoint is not None else None,
            "embedded_nodata": str(nodata) if nodata is not None else None,
            "image_description": page.description or None,
            "derived_georeferencing": derived_georeferencing,
        }


def _manifest_rows() -> list[dict[str, str]]:
    with (DATA_DIR / "manifest.csv").open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def _vector_metadata(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    features = document.get("features", [])
    properties = [feature.get("properties") or {} for feature in features]
    coordinates: list[tuple[float, float]] = []

    def visit(value: Any) -> None:
        if isinstance(value, (list, tuple)):
            if len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
                coordinates.append((float(value[0]), float(value[1])))
            else:
                for child in value:
                    visit(child)

    for feature in features:
        visit((feature.get("geometry") or {}).get("coordinates"))
    crs = (document.get("crs") or {}).get("properties", {}).get("name")
    layer_name = path.name
    source_key = {
        "habitations_target_districts.geojson": "id",
        "facilities_target_districts.geojson": None,
        "roads_target_districts.geojson": "er_id",
        "district_boundaries.geojson": "lgd_code",
    }.get(layer_name)
    missing_primary_ids = (
        sum(record.get(source_key) in (None, "") for record in properties)
        if source_key
        else 0
    )
    if layer_name == "facilities_target_districts.geojson":
        missing_primary_ids = sum(
            record.get("nic_source_id") in (None, "")
            and record.get("pmgsy_source_id") in (None, "")
            for record in properties
        )
    return {
        "feature_count": len(features),
        "declared_crs": crs,
        "observed_coordinate_bounds": (
            [
                min(lon for lon, _ in coordinates),
                min(lat for _, lat in coordinates),
                max(lon for lon, _ in coordinates),
                max(lat for _, lat in coordinates),
            ]
            if coordinates
            else None
        ),
        "missing_source_id_count": missing_primary_ids,
        "district_counts": {
            district: sum(
                record.get("district", record.get("district_name")) == district
                for record in properties
            )
            for district in ("Chamoli", "Pithoragarh", "Rudraprayag")
        },
        "property_names": sorted({key for record in properties for key in record}),
    }


def shapefile_archive_metadata(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        projection_files = [
            name for name in names
            if name.lower().endswith(".prj") and not name.endswith("/")
        ]
        return {
            "entry_count": len(names),
            "shapefile_components": [
                name for name in names
                if name.lower().endswith((".shp", ".shx", ".dbf", ".prj", ".cpg"))
            ][:200],
            "projection_files": {
                name: archive.read(name).decode("utf-8", errors="replace")[:4000]
                for name in projection_files
            },
        }


def run(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty audit directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _manifest_rows()
    datasets: list[dict[str, Any]] = []
    for entry in manifest:
        raw_paths = [DATA_DIR.parent / Path(item.strip()) for item in entry["raw_file"].split(",")]
        processed_paths = [
            DATA_DIR.parent / Path(item.strip())
            for item in entry["processed_file"].split(",")
        ]
        record: dict[str, Any] = {
            "dataset_name": entry["dataset_name"],
            "entity_type": entry["entity_type"],
            "manifest_publisher_attribution": entry["primary_authority"],
            "manifest_source_url": entry["source_url"],
            "manifest_download_date": entry["download_date"],
            "manifest_license_claim": entry["license"],
            "manifest_coverage_claim": entry["geographic_coverage"],
            "manifest_crs_claim": entry["crs"],
            "raw_files": [],
            "processed_files": [],
            "manifest_record_count": entry["record_count"],
            "manifest_processing_description": entry["processing_steps"],
            "provenance_assessment": "Manifest claims are not independent proof of record-level origin or licensing.",
        }
        for path in raw_paths:
            item: dict[str, Any] = {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "exists": path.is_file(),
            }
            if path.is_file():
                item.update({"bytes": path.stat().st_size, "sha256": sha256(path)})
                if path.suffix.lower() in (".tif", ".tiff"):
                    item["raster_metadata"] = raster_facts(path)
                if path.suffix.lower() == ".zip":
                    item["archive_metadata"] = shapefile_archive_metadata(path)
            record["raw_files"].append(item)
        for path in processed_paths:
            item = {"path": str(path.relative_to(PROJECT_ROOT)), "exists": path.is_file()}
            if path.is_file():
                item.update({"bytes": path.stat().st_size, "sha256": sha256(path)})
                if path.suffix.lower() == ".geojson":
                    try:
                        item["vector_metadata"] = _vector_metadata(path)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        item["metadata_error"] = "GeoJSON metadata could not be parsed."
                elif path.suffix.lower() == ".json":
                    item["sidecar_metadata"] = json.loads(path.read_text(encoding="utf-8"))
                elif path.suffix.lower() in (".tif", ".tiff"):
                    item["raster_metadata"] = raster_facts(path)
            record["processed_files"].append(item)
        datasets.append(record)

    inventory_path = DATA_DIR / "audit_phase1_20261020" / "source_hash_inventory.csv"
    hash_matches = 0
    hash_failures: list[dict[str, str]] = []
    if inventory_path.is_file():
        with inventory_path.open(newline="", encoding="utf-8-sig") as source:
            for row in csv.DictReader(source):
                candidate = PROJECT_ROOT / Path(row["relative_path"])
                actual = sha256(candidate) if candidate.is_file() else "missing"
                if actual == row["active_sha256"].strip().lower():
                    hash_matches += 1
                else:
                    hash_failures.append({
                        "path": row["relative_path"],
                        "expected": row["active_sha256"],
                        "actual": actual,
                    })

    issues = [
        {
            "issue_id": "FACILITY-501-484",
            "severity": "high",
            "dataset": "Processed facilities",
            "status": "unresolved",
            "verified_fact": "Manifest declares 501, while processed CSV and GeoJSON each contain 484.",
            "known_reproduction": "Phase 1 local replay produced 503 with the earlier dedupe and 484 with refined filtering.",
            "unknown": "The exact provenance and operation responsible for manifest count 501 are not present in the files reviewed.",
            "action": "Keep all 484 processed rows; review source IDs, candidate inclusion, and the undocumented count difference.",
        },
        {
            "issue_id": "FACILITY-SOURCE-LABELS",
            "severity": "high",
            "dataset": "Processed facilities",
            "status": "unresolved",
            "verified_fact": "484 rows carry 172 NIC IDs and 316 PMGSY IDs; 4 rows carry both, and 51 rows labeled combined have only PMGSY IDs.",
            "known_reproduction": "The Phase 1 facility reconciliation records 168 NIC-only, 55 combined-labeled, and 261 PMGSY-labeled rows.",
            "unknown": "A provider or source label does not establish record-level original origin or authority verification.",
            "action": "Retain both identifier fields and source labels; resolve record-level lineage before asserting authority.",
        },
        {
            "issue_id": "PROCESSED-SOURCE-IDS",
            "severity": "low",
            "dataset": "Processed habitation, facility, road, and district vectors",
            "status": "no-missing-primary-ids-found",
            "verified_fact": "The processed vector layers have zero missing primary identifiers under the current schema-specific checks.",
            "known_reproduction": "Habitation id: 0/3,368 missing; facility has both NIC/PMGSY ID fields absent: 0/484; road er_id: 0/2,309; boundary lgd_code: 0/3.",
            "unknown": "Identifier presence does not authenticate the issuer, identifier namespace, or source-record lineage.",
            "action": "Preserve all IDs and verify namespaces/lineage independently before calling them official IDs.",
        },
        {
            "issue_id": "HABITATION-BOUNDARY-9",
            "severity": "medium",
            "dataset": "Processed habitations",
            "status": "review-required",
            "verified_fact": "Nine source habitations are outside their assigned district polygon in the Phase 1 spatial check.",
            "known_reproduction": "Two Chamoli, two Pithoragarh, and five Rudraprayag records; IDs and coordinates are in the review CSV.",
            "unknown": "Whether the cause is boundary version, coordinate error, or assignment error.",
            "action": "Preserve source coordinates and district assignment; seek source-owner clarification.",
        },
        {
            "issue_id": "PITHORAGARH-DEM-EDGE",
            "severity": "high",
            "dataset": "Pithoragarh DEM",
            "status": "coverage-limited",
            "verified_fact": "Phase 2A masks 24,548 non-nodata processed source cells unsupported by locally stored verified DEM tiles; zero valid output pixels remain east of the source edge.",
            "known_reproduction": "Derived copy is EPSG:32644, 30 m; boundary validator recorded zero valid pixel centers outside the district polygon.",
            "unknown": "Terrain beyond the verified raw tile coverage is unobserved in this local source set.",
            "action": "Keep the masked edge inaccessible/unknown; obtain an authoritative additional tile only through a separately approved, licensed data update.",
        },
        {
            "issue_id": "MIRROR-PROVENANCE",
            "severity": "high",
            "dataset": "NIC/PMGSY vectors and WorldPop raster",
            "status": "unverified-lineage",
            "verified_fact": "Manifest URLs point to a personal GitHub repository/release rather than directly to the named government agency or WorldPop host.",
            "known_reproduction": "Local raw NIC GeoJSON contains 147,957 features but has no CRS declaration; processed project GeoJSON declares CRS84.",
            "unknown": "A signed/source-publisher checksum, capture date/version, and license grant for each mirrored artifact were not found in local metadata.",
            "action": "Treat provider, version, date, and license as manifest assertions until matched to an official downloadable artifact and terms.",
        },
        {
            "issue_id": "WORLDPOP-VERSION",
            "severity": "medium",
            "dataset": "WorldPop population raster",
            "status": "unverified-lineage",
            "verified_fact": "Local raw TIFF has 30-arc-second pixel-scale tags, a WGS84-like geographic tiepoint, and nodata -99999; filename says 2020/1km.",
            "known_reproduction": "Official WorldPop page for DOI 10.5258/SOTON/WP00647 describes WGS84 population estimates per cell at 30 arc-seconds, but it does not establish this local file's exact identity.",
            "unknown": "The local TIFF has no embedded CRS GeoKey and no source DOI/license metadata sufficient to prove the claimed product/version or interpretation.",
            "action": "Do not assign raster density/counts to habitations. Verify the exact product and license before analytical use.",
        },
        {
            "issue_id": "DEM-PRODUCT-TYPE",
            "severity": "medium",
            "dataset": "Copernicus DEM",
            "status": "limitation",
            "verified_fact": "Official Copernicus documentation describes GLO-30 as a DSM (top-reflective surface), acquired by TanDEM-X during 2011-2015; local files are five named one-degree TIFFs.",
            "known_reproduction": "The project phase2a report ties exact georeferenced derived copies to local raw tile pixel windows and masks unsupported cells.",
            "unknown": "The manifest's stated CC-BY-SA license and individual raw tile acquisition/version are not authenticated by a local license/metadata record.",
            "action": "Cite the official product facts, disclose DSM limitations, and verify release-specific license terms for redistribution.",
        },
        {
            "issue_id": "ROAD-ROUTING-UNVERIFIED",
            "severity": "medium",
            "dataset": "Processed roads",
            "status": "not-a-routing-graph",
            "verified_fact": "2,309 valid source LineString features; prior diagnostics found duplicate er_id rows and 2D intersection pairs.",
            "known_reproduction": "2D intersections do not resolve grade separation, bridges, endpoint snapping, or network directionality.",
            "unknown": "Connectivity and travel speed provenance are not verified.",
            "action": "Do not claim road-network distance or travel time from these geometries.",
        },
    ]

    with (output_dir / "dataset_inventory.csv").open("w", newline="", encoding="utf-8") as output:
        fields = (
            "dataset_name", "entity_type", "manifest_publisher_attribution", "manifest_source_url",
            "manifest_download_date", "manifest_license_claim", "manifest_coverage_claim",
            "manifest_crs_claim", "manifest_record_count", "provenance_assessment",
            "raw_files_json", "processed_files_json",
        )
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for dataset in datasets:
            row = dict(dataset)
            row["raw_files_json"] = json.dumps(row.pop("raw_files"), sort_keys=True)
            row["processed_files_json"] = json.dumps(row.pop("processed_files"), sort_keys=True)
            writer.writerow({key: row.get(key) for key in fields})

    issue_fields = (
        "issue_id", "severity", "dataset", "status", "verified_fact",
        "known_reproduction", "unknown", "action",
    )
    with (output_dir / "data_issues.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=issue_fields)
        writer.writeheader()
        writer.writerows(issues)

    outliers_path = DATA_DIR / "audit_phase1_20261020" / "habitation_district_outliers.csv"
    if outliers_path.is_file():
        with outliers_path.open("r", encoding="utf-8-sig", newline="") as source:
            with (output_dir / "habitation_boundary_reviews.csv").open(
                "w", encoding="utf-8", newline=""
            ) as target:
                target.write(source.read())
    facility_source = DATA_DIR / "audit_phase1_20261020" / "facility_reconciliation.csv"
    if facility_source.is_file():
        with facility_source.open("r", encoding="utf-8-sig", newline="") as source:
            with (output_dir / "facility_reconciliation.csv").open(
                "w", encoding="utf-8", newline=""
            ) as target:
                target.write(source.read())

    report = {
        "title": "HillCare Access real-data provenance audit",
        "audit_date": "2026-10-20",
        "dataset_count": len(datasets),
        "issues": issues,
        "source_hash_inventory": {
            "files_matching_phase1": hash_matches,
            "mismatches_or_missing": hash_failures,
        },
        "official_documentation_checked": [
            {
                "provider": "Copernicus Data Space Ecosystem",
                "url": "https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM",
                "verified": "Copernicus DEM product page describes GLO-30/GLO-90, DSM/top-reflective surface, and TanDEM-X acquisitions 2011-2015. It states GLO-30/GLO-90 are freely available under the stated user obligations and supplies mandatory source/adaptation attribution; individual source tile release identity is not independently established.",
            },
            {
                "provider": "WorldPop",
                "url": "https://hub.worldpop.org/geodata/summary?id=24777",
                "verified": "That product page describes WGS84 and 30 arc-second population estimates per cell under DOI 10.5258/SOTON/WP00647; exact local TIFF match is not established.",
            },
            {
                "provider": "OpenStreetMap Foundation",
                "url": "https://www.openstreetmap.org/copyright",
                "verified": "OSM attribution page states ODbL licensing; no OSM dataset is used or automatically synchronized by this workflow.",
            },
            {
                "provider": "NIC HealthGIS / MoHFW and PMGSY GeoSadak",
                "urls_checked": ["https://healthgis.mohfw.gov.in/", "https://geosadak-pmgsy.nic.in/"],
                "verified": "Official endpoints could not be retrieved in this environment; portal access, update mechanisms, and data terms remain unverified.",
            },
        ],
    }
    (output_dir / "provenance_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md = [
        "# Real-data provenance and issue audit",
        "",
        "## Evidence standard",
        "",
        "A local manifest label or source property is an attribution claim, not proof that an individual record was authored, verified, or licensed by the named organization. Hashes identify local bytes but do not prove publisher origin.",
        "",
        f"Phase 1 input-hash inventory comparison: **{hash_matches} matches, {len(hash_failures)} mismatches or missing files**.",
        "",
        "## Verified local facts and official product facts",
        "",
        "- Processed features retain declared CRS84 coordinates. The local NIC source GeoJSON itself has no CRS declaration; raw processed transformations therefore rely on the documented pipeline and cross-checks, not an embedded source declaration.",
        "- Processed habitation / facility / road / boundary feature totals are 3,368 / 484 / 2,309 / 3. Schema-specific checks found zero missing primary IDs, but ID provenance is not verified. The original manifest declares 501 facilities.",
        "- All nine known habitation boundary-review records are copied without editing into `habitation_boundary_reviews.csv`.",
        "- Phase 2A validates three 30 m EPSG:32644 district DEM copies. Pithoragarh has 24,548 unsupported source cells masked, and no valid output pixels east of the locally verified raw-tile edge.",
        "- Official Copernicus documentation identifies GLO-30 as a DSM/top-reflective surface, with TanDEM-X acquisition during 2011-2015. The product page describes GLO-30 as freely available with attribution obligations; verify exact tile/release identity. It is not a bare-earth terrain model.",
        "- An official WorldPop product page exists for DOI 10.5258/SOTON/WP00647; it cannot establish that the local raw file is exactly that product/version. WorldPop values are not attached to habitation records.",
        "",
        "## Unresolved provenance and issues",
        "",
        "The manifest URLs for NIC/PMGSY vectors and the WorldPop raster point to a third-party GitHub mirror. Local file hashes establish only the current file identity. Record-level publisher lineage, release date/version, and license terms remain unverified. NIC and PMGSY official portal endpoints could not be accessed during this audit. No automatic synchronization was implemented.",
        "",
        "See `data_issues.csv` for evidence status and actions; `dataset_inventory.csv` for manifest claims, file hashes and observed schema/metadata; `facility_reconciliation.csv` and `habitation_boundary_reviews.csv` for row-level reconciliation. Original datasets were not modified.",
        "",
        "## Manual update recommendation",
        "",
        "Request versioned exports and explicit license/redistribution terms from the responsible state/district office or official data portal. Store each received package read-only with download timestamp, source URL/contact, license notice, checksum, and schema; import into a new staged snapshot; preview added/changed/removed records and spatial validation issues; require a reviewer decision before replacing any published snapshot. For OpenStreetMap extracts, preserve ODbL attribution/share-alike obligations and record the extract timestamp; do not rely on public tile endpoints as a data API.",
        "",
    ]
    (output_dir / "provenance_audit_report.md").write_text("\n".join(md), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output_dir)
    print(json.dumps({
        "output_dir": str(args.output_dir.resolve()),
        "datasets": report["dataset_count"],
        "issues": len(report["issues"]),
        "hash_matches": report["source_hash_inventory"]["files_matching_phase1"],
    }, indent=2))


if __name__ == "__main__":
    main()
