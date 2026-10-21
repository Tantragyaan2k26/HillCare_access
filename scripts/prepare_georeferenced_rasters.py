"""Create verified, georeferenced Phase 2A raster copies.

The original files in data/raw and data/processed are never modified.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from shapely.geometry import shape
from shapely.ops import transform as transform_geometry

if __package__:
    from .phase2a_raster_utils import (
        RasterMetadata,
        read_geotiff_metadata,
        source_coverage_mask,
        valid_pixel_boundary_violations,
        validate_geotiff,
        write_geotiff,
    )
else:
    from phase2a_raster_utils import (
        RasterMetadata,
        read_geotiff_metadata,
        source_coverage_mask,
        valid_pixel_boundary_violations,
        validate_geotiff,
        write_geotiff,
    )


DISTRICTS = ("Chamoli", "Pithoragarh", "Rudraprayag")
PIXEL_SIZE_ARC_SECONDS = 1.0
DEM_NODATA = -9999.0
DEM_TILES = {
    ("N30", "E078"): (0, 0),
    ("N30", "E079"): (0, 3600),
    ("N30", "E080"): (0, 7200),
    ("N29", "E079"): (3600, 3600),
    ("N29", "E080"): (3600, 7200),
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_dem_sidecar(processed_dir: Path, district: str) -> tuple[Path, dict[str, Any]]:
    stem = f"dem_{district.lower()}_utm44n"
    raster_path = processed_dir / f"{stem}.tif"
    sidecar_path = processed_dir / f"{stem}.json"
    metadata = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if metadata.get("district") != district or metadata.get("crs") != "EPSG:32644":
        raise ValueError(f"{sidecar_path} does not declare the expected district and CRS.")
    transform = tuple(float(value) for value in metadata["transform"])
    rows, cols = (int(value) for value in metadata["shape"])
    if len(transform) != 6 or transform[0] != 30.0 or transform[4] != -30.0:
        raise ValueError(f"{sidecar_path} has an unsupported affine transform.")
    if metadata["pixel_size_meters"] != 30.0 or metadata["nodata"] != DEM_NODATA:
        raise ValueError(f"{sidecar_path} has an unexpected pixel size or nodata value.")
    if (rows, cols) != tuple(tifffile.memmap(raster_path).shape):
        raise ValueError(f"{raster_path} dimensions disagree with its sidecar.")
    x0, y0, x1, y1 = metadata["bounds_utm44n"]
    expected_bounds = (
        transform[2],
        transform[5] + rows * transform[4],
        transform[2] + cols * transform[0],
        transform[5],
    )
    if not np.allclose((x0, y0, x1, y1), expected_bounds, rtol=0.0, atol=1e-7):
        raise ValueError(f"{sidecar_path} bounds disagree with its affine transform.")
    return raster_path, metadata


def _read_verified_tiles(raw_dem_dir: Path) -> tuple[list[dict[str, Any]], list[tuple[float, float, float, float]]]:
    tiles: list[dict[str, Any]] = []
    bounds: list[tuple[float, float, float, float]] = []
    for (lat_id, lon_id), (mosaic_row, mosaic_col) in DEM_TILES.items():
        path = raw_dem_dir / f"Copernicus_DSM_COG_10_{lat_id}_00_{lon_id}_00_DEM.tif"
        with tifffile.TiffFile(path) as tif:
            page = tif.pages[0]
            actual = read_geotiff_metadata(
                path,
                require_nodata=False,
                allow_pixel_is_point=True,
            )
            if page.shape != (3600, 3600) or actual.crs_epsg != 4326:
                raise ValueError(f"{path} does not match the verified 1-degree EPSG:4326 tile grid.")
            expected_scale = PIXEL_SIZE_ARC_SECONDS / 3600.0
            if not np.allclose(actual.transform[:2] + actual.transform[3:5],
                               (expected_scale, 0.0, 0.0, -expected_scale),
                               rtol=0.0, atol=1e-12):
                raise ValueError(f"{path} has an unexpected Copernicus pixel scale.")
            west = 78.0 + mosaic_col / 3600.0
            north = 31.0 - mosaic_row / 3600.0
            source_center_x = actual.transform[2] + expected_scale / 2.0
            source_center_y = actual.transform[5] - expected_scale / 2.0
            if not math.isclose(source_center_x, west, abs_tol=1e-10) or not math.isclose(
                source_center_y, north, abs_tol=1e-10
            ):
                raise ValueError(f"{path} tiepoint does not match its declared mosaic position.")
            east = west + page.shape[1] * expected_scale
            south = north - page.shape[0] * expected_scale
            bounds.append((west, south, east, north))
            tiles.append({
                "path": path,
                "row": mosaic_row,
                "col": mosaic_col,
                "shape": page.shape,
                "bounds": (west, south, east, north),
            })
    return tiles, bounds


def _verify_and_prepare_aggregate_dem(
    processed_dir: Path,
    tiles: list[dict[str, Any]],
    output_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    top, bottom, left, right = 30.85, 29.40, 78.80, 80.90
    scale = 1.0 / 3600.0
    row0 = int((31.0 - top) * 3600)
    row1 = int((31.0 - bottom) * 3600)
    col0 = int((left - 78.0) * 3600)
    col1 = int((right - 78.0) * 3600)
    source_path = processed_dir / "dem_target_districts.tif"
    source = tifffile.memmap(source_path)
    expected_shape = (row1 - row0, col1 - col0)
    if source.shape != expected_shape or source.dtype != np.float32:
        raise ValueError(f"{source_path} dimensions do not match the recorded crop parameters.")

    covered = np.zeros(expected_shape, dtype=bool)
    for tile in tiles:
        tile_row, tile_col = tile["row"], tile["col"]
        row_start = max(row0, tile_row)
        row_end = min(row1, tile_row + tile["shape"][0])
        col_start = max(col0, tile_col)
        col_end = min(col1, tile_col + tile["shape"][1])
        if row_start >= row_end or col_start >= col_end:
            continue
        with tifffile.TiffFile(tile["path"]) as tif:
            raw = tif.pages[0].asarray()
        out_rows = slice(row_start - row0, row_end - row0)
        out_cols = slice(col_start - col0, col_end - col0)
        raw_rows = slice(row_start - tile_row, row_end - tile_row)
        raw_cols = slice(col_start - tile_col, col_end - tile_col)
        if not np.array_equal(source[out_rows, out_cols], raw[raw_rows, raw_cols]):
            raise ValueError(f"{source_path} does not match its raw Copernicus tile window.")
        covered[out_rows, out_cols] = True

    if np.any(source[~covered] != DEM_NODATA):
        raise ValueError(f"{source_path} contains values outside verified raw tile coverage.")

    output_path = output_dir / source_path.name
    affine = (scale, 0.0, 78.0 + col0 * scale, 0.0, -scale, 31.0 - row0 * scale)
    return output_path, {
        "source": source_path,
        "data": source,
        "crs_epsg": 4326,
        "transform": affine,
        "nodata": DEM_NODATA,
        "shape": expected_shape,
        "description": "Verified crop of local Copernicus 1-arc-second DEM mosaic.",
        "source_coverage_mask": covered,
    }


def _verify_and_prepare_worldpop(processed_dir: Path, raw_dir: Path, output_dir: Path) -> tuple[Path, dict[str, Any]]:
    source_path = processed_dir / "population_density_target_districts.tif"
    raw_path = raw_dir / "ind_pd_2020_1km.tif"
    with tifffile.TiffFile(raw_path) as tif:
        page = tif.pages[0]
        raw_data = page.asarray()
        tags = page.tags
        keys = tags["GeoKeyDirectoryTag"].value
        geo_keys = {keys[i]: keys[i + 3] for i in range(4, len(keys), 4)}
        if geo_keys.get(2048) != 4326:
            raise ValueError(f"{raw_path} does not declare EPSG:4326.")
        scale_tag = tags["ModelPixelScaleTag"].value
        tiepoint = tags["ModelTiepointTag"].value
        nodata_tag = tags.get("GDAL_NODATA")
        if len(scale_tag) < 2 or len(tiepoint) < 6 or nodata_tag is None:
            raise ValueError(f"{raw_path} is missing required georeferencing or nodata tags.")
        sx, sy = float(scale_tag[0]), float(scale_tag[1])
        origin_x, origin_y = float(tiepoint[3]), float(tiepoint[4])
        nodata_value = nodata_tag.value
        if isinstance(nodata_value, bytes):
            nodata_value = nodata_value.decode("ascii")
        nodata = float(str(nodata_value).rstrip("\x00"))
        crop_left, crop_right, crop_top, crop_bottom = 78.80, 80.90, 30.85, 29.40
        col0 = max(0, int((crop_left - origin_x) / sx))
        col1 = min(raw_data.shape[1], int((crop_right - origin_x) / sx))
        row0 = max(0, int((origin_y - crop_top) / sy))
        row1 = min(raw_data.shape[0], int((origin_y - crop_bottom) / sy))
        expected = raw_data[row0:row1, col0:col1]

    processed = tifffile.memmap(source_path)
    if processed.shape != expected.shape or not np.array_equal(processed, expected):
        raise ValueError(f"{source_path} is not the crop implied by the raw WorldPop georeferencing.")
    output_path = output_dir / source_path.name
    return output_path, {
        "source": source_path,
        "data": processed,
        "crs_epsg": 4326,
        "transform": (sx, 0.0, origin_x + col0 * sx, 0.0, -sy, origin_y - row0 * sy),
        "nodata": nodata,
        "shape": tuple(processed.shape),
        "description": "Verified raw WorldPop window; no resampling or reprojection.",
    }


def _check_district_coverage(
    data: np.ndarray,
    metadata: RasterMetadata,
    polygon_wgs84: Any,
) -> int:
    from pyproj import Transformer

    transformer = Transformer.from_crs(4326, metadata.crs_epsg, always_xy=True)
    projected_polygon = transform_geometry(transformer.transform, polygon_wgs84)
    x_scale, _, x_origin, _, y_scale, y_origin = metadata.transform
    raster_bounds = (
        x_origin,
        y_origin + data.shape[0] * y_scale,
        x_origin + data.shape[1] * x_scale,
        y_origin,
    )
    minx, miny, maxx, maxy = projected_polygon.bounds
    if raster_bounds[0] > minx or raster_bounds[1] > miny or raster_bounds[2] < maxx or raster_bounds[3] < maxy:
        raise ValueError(f"Raster extent does not cover the {polygon_wgs84} district polygon bounds.")
    return valid_pixel_boundary_violations(
        data,
        nodata=metadata.nodata,
        transform=metadata.transform,
        crs_epsg=metadata.crs_epsg,
        boundary=polygon_wgs84,
    )


def prepare(output_dir: Path | None = None) -> Path:
    root = project_root()
    processed_dir = root / "data" / "processed"
    raw_dir = root / "data" / "raw"
    output_dir = output_dir or root / "data" / "processed_phase2a"
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 2A output directory: {output_dir}")

    tiles, source_bounds = _read_verified_tiles(raw_dir / "dem")
    districts_path = processed_dir / "district_boundaries.geojson"
    boundary_data = json.loads(districts_path.read_text(encoding="utf-8"))
    polygons = {
        feature["properties"]["district_name"]: shape(feature["geometry"])
        for feature in boundary_data["features"]
    }
    if set(polygons) != set(DISTRICTS):
        raise ValueError("District boundary file does not contain exactly the three pilot districts.")

    aggregate_path, aggregate = _verify_and_prepare_aggregate_dem(processed_dir, tiles, output_dir)
    worldpop_path, worldpop = _verify_and_prepare_worldpop(processed_dir, raw_dir, output_dir)

    district_inputs: list[tuple[Path, Path, dict[str, Any], np.ndarray]] = []
    for district in DISTRICTS:
        source_path, sidecar = _read_dem_sidecar(processed_dir, district)
        data = tifffile.memmap(source_path)
        supported = source_coverage_mask(
            tuple(data.shape),
            sidecar["transform"],
            32644,
            source_bounds,
        )
        derived = np.array(data, dtype=np.float32, copy=True)
        derived[~supported] = DEM_NODATA
        output_path = output_dir / source_path.name
        district_inputs.append((source_path, output_path, sidecar, derived))

    output_dir.mkdir(parents=True)
    report: dict[str, Any] = {
        "phase": "2A",
        "inputs_unchanged": True,
        "aggregate_dem": {
            "source": str(aggregate["source"].relative_to(root)),
            "crs": "EPSG:4326",
            "transform": aggregate["transform"],
            "pixel_size_degrees": 1.0 / 3600.0,
            "nodata": aggregate["nodata"],
            "raw_tile_window_verified": True,
        },
        "worldpop": {
            "source": str(worldpop["source"].relative_to(root)),
            "crs": "EPSG:4326",
            "transform": worldpop["transform"],
            "pixel_size_degrees": [worldpop["transform"][0], abs(worldpop["transform"][4])],
            "nodata": worldpop["nodata"],
            "raw_window_verified": True,
        },
        "district_dems": {},
    }

    write_geotiff(
        aggregate_path,
        aggregate["data"],
        crs_epsg=aggregate["crs_epsg"],
        transform=aggregate["transform"],
        nodata=aggregate["nodata"],
        description=aggregate["description"],
    )
    write_geotiff(
        worldpop_path,
        worldpop["data"],
        crs_epsg=worldpop["crs_epsg"],
        transform=worldpop["transform"],
        nodata=worldpop["nodata"],
        description=worldpop["description"],
    )
    for source_path, output_path, sidecar, derived in district_inputs:
        write_geotiff(
            output_path,
            derived,
            crs_epsg=32644,
            transform=sidecar["transform"],
            nodata=DEM_NODATA,
            description=f"Georeferenced copy of {source_path.name}; unsupported raw-source cells set to nodata.",
        )
        unsupported = int(np.count_nonzero(
            (tifffile.memmap(source_path) != DEM_NODATA)
            & (derived == DEM_NODATA)
        ))
        report["district_dems"][sidecar["district"]] = {
            "source": str(source_path.relative_to(root)),
            "crs": sidecar["crs"],
            "transform": sidecar["transform"],
            "shape": sidecar["shape"],
            "pixel_size_meters": sidecar["pixel_size_meters"],
            "nodata": DEM_NODATA,
            "unsupported_source_cells_marked_nodata": unsupported,
        }

    validation = validate_outputs(root, output_dir, source_bounds, polygons)
    report["validation"] = validation
    (output_dir / "phase2a_validation_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_dir


def validate_outputs(
    root: Path | None = None,
    output_dir: Path | None = None,
    source_bounds: list[tuple[float, float, float, float]] | None = None,
    polygons: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root or project_root()
    processed_dir = root / "data" / "processed"
    raw_dir = root / "data" / "raw"
    output_dir = output_dir or root / "data" / "processed_phase2a"
    if source_bounds is None:
        _, source_bounds = _read_verified_tiles(raw_dir / "dem")
    if polygons is None:
        boundary_data = json.loads((processed_dir / "district_boundaries.geojson").read_text(encoding="utf-8"))
        polygons = {
            feature["properties"]["district_name"]: shape(feature["geometry"])
            for feature in boundary_data["features"]
        }

    results: dict[str, Any] = {}
    aggregate_path, aggregate = _verify_and_prepare_aggregate_dem(processed_dir, _read_verified_tiles(raw_dir / "dem")[0], output_dir)
    expected = RasterMetadata(aggregate["crs_epsg"], aggregate["transform"], aggregate["nodata"], aggregate["shape"])
    aggregate_data = validate_geotiff(aggregate_path, expected)
    if not np.array_equal(aggregate_data, aggregate["data"]):
        raise ValueError("Georeferenced aggregate DEM pixels differ from verified raw tile sources.")
    results[aggregate_path.name] = {"shape": expected.shape, "valid_pixels": int(np.count_nonzero(aggregate_data != expected.nodata))}

    worldpop_path, worldpop = _verify_and_prepare_worldpop(processed_dir, raw_dir, output_dir)
    expected = RasterMetadata(worldpop["crs_epsg"], worldpop["transform"], worldpop["nodata"], worldpop["shape"])
    pop_data = validate_geotiff(worldpop_path, expected)
    if not np.array_equal(pop_data, worldpop["data"]):
        raise ValueError("Georeferenced WorldPop pixels differ from the verified raw source window.")
    results[worldpop_path.name] = {"shape": expected.shape, "valid_pixels": int(np.count_nonzero(pop_data != expected.nodata))}

    for district in DISTRICTS:
        source_path, sidecar = _read_dem_sidecar(processed_dir, district)
        output_path = output_dir / source_path.name
        expected = RasterMetadata(32644, tuple(sidecar["transform"]), DEM_NODATA, tuple(sidecar["shape"]))
        data = validate_geotiff(output_path, expected)
        source = tifffile.memmap(source_path)
        supported = source_coverage_mask(
            tuple(source.shape),
            sidecar["transform"],
            32644,
            source_bounds,
        )
        source_valid = np.isfinite(source) & (source != DEM_NODATA)
        expected_data = np.array(source, dtype=np.float32, copy=True)
        expected_data[~supported] = DEM_NODATA
        if not np.array_equal(data, expected_data):
            raise ValueError(f"{output_path} pixel values/mask do not match supported source DEM cells.")
        violations = _check_district_coverage(data, expected, polygons[district])
        if violations:
            raise ValueError(f"{output_path} has {violations} valid pixel centers outside its district polygon.")
        unsupported_valid = int(np.count_nonzero(source_valid & ~supported))
        results[output_path.name] = {
            "shape": expected.shape,
            "valid_pixels": int(np.count_nonzero(data != DEM_NODATA)),
            "district_boundary_violations": violations,
            "unsupported_source_valid_pixels_masked": unsupported_valid,
        }
        if district == "Pithoragarh":
            x_scale, _, x_origin, _, y_scale, y_origin = expected.transform
            to_lon = TransformerForCoverage()
            centers_x = x_origin + (np.arange(source.shape[1]) + 0.5) * x_scale
            east_valid = 0
            for row in range(source.shape[0]):
                northing = y_origin + (row + 0.5) * y_scale
                longitude, _ = to_lon.transform(
                    centers_x,
                    np.full(source.shape[1], northing, dtype=np.float64),
                )
                east_valid += int(np.count_nonzero(
                    (longitude >= 81.0) & (data[row] != DEM_NODATA)
                ))
            if east_valid:
                raise ValueError("Pithoragarh contains valid pixels east of the 81-degree raw DEM edge.")
            results[output_path.name]["valid_pixels_east_of_raw_coverage_edge"] = east_valid
    return results


def TransformerForCoverage():
    from pyproj import Transformer

    return Transformer.from_crs(32644, 4326, always_xy=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="New output directory (must not already exist).")
    args = parser.parse_args()
    output = prepare(args.output_dir)
    print(f"Created and validated derived rasters in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
