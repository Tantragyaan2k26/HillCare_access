"""Shared GeoTIFF metadata and validation helpers for Phase 2A."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import tifffile
from pyproj import Transformer
from shapely import covers, points
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class RasterMetadata:
    crs_epsg: int
    transform: tuple[float, float, float, float, float, float]
    nodata: float
    shape: tuple[int, int]


def write_geotiff(
    path: Path,
    data: np.ndarray,
    *,
    crs_epsg: int,
    transform: Sequence[float],
    nodata: float,
    description: str,
) -> None:
    """Write a single-band float32 GeoTIFF with embedded GeoTIFF tags."""
    if data.ndim != 2 or data.dtype != np.float32:
        raise ValueError("GeoTIFF data must be a two-dimensional float32 array.")
    if len(transform) != 6:
        raise ValueError("Affine transform must contain six coefficients.")
    x_scale, x_shear, x_origin, y_shear, y_scale, y_origin = transform
    if x_scale <= 0 or y_scale >= 0 or x_shear != 0 or y_shear != 0:
        raise ValueError("Only north-up, unrotated rasters are supported.")

    if crs_epsg not in (4326, 32644):
        raise ValueError(f"Unsupported CRS for Phase 2A GeoTIFF output: EPSG:{crs_epsg}.")
    model_type = 1 if crs_epsg == 32644 else 2
    crs_key = 3072 if model_type == 1 else 2048
    geo_keys = (1, 1, 0, 3, 1024, 0, 1, model_type,
                1025, 0, 1, 1, crs_key, 0, 1, crs_epsg)
    tifffile.imwrite(
        path,
        data,
        photometric="minisblack",
        metadata=None,
        description=description,
        extratags=[
            (33550, "d", 3, (x_scale, abs(y_scale), 0.0), False),
            (33922, "d", 6, (0.0, 0.0, 0.0, x_origin, y_origin, 0.0), False),
            (34735, "H", len(geo_keys), geo_keys, False),
            (42113, "s", 0, f"{nodata:g}\x00", False),
        ],
    )


def read_geotiff_metadata(
    path: Path,
    *,
    require_nodata: bool = True,
    allow_pixel_is_point: bool = False,
) -> RasterMetadata:
    """Read and validate the GeoTIFF CRS, north-up transform, and nodata tags."""
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        tags = page.tags
        required = ("GeoKeyDirectoryTag", "ModelPixelScaleTag", "ModelTiepointTag")
        if require_nodata:
            required += ("GDAL_NODATA",)
        missing = [name for name in required if name not in tags]
        if missing:
            raise ValueError(f"{path} is missing GeoTIFF tags: {', '.join(missing)}")

        geo_keys = tags["GeoKeyDirectoryTag"].value
        if len(geo_keys) < 4 or geo_keys[:3] != (1, 1, 0):
            raise ValueError(f"{path} has an unsupported GeoKeyDirectory version.")
        key_count = geo_keys[3]
        if len(geo_keys) != 4 + key_count * 4:
            raise ValueError(f"{path} has an incomplete GeoKeyDirectory.")
        key_values = {
            geo_keys[offset]: geo_keys[offset + 3]
            for offset in range(4, 4 + key_count * 4, 4)
        }
        model_type = key_values.get(1024)
        raster_type = key_values.get(1025)
        if model_type not in (1, 2) or raster_type not in (1, 2):
            raise ValueError(f"{path} must declare a projected/geographic CRS and raster type.")
        if raster_type == 2 and not allow_pixel_is_point:
            raise ValueError(f"{path} declares PixelIsPoint; an area-grid raster is required.")
        crs_epsg = key_values.get(3072 if model_type == 1 else 2048)
        if crs_epsg is None:
            raise ValueError(f"{path} does not declare an EPSG CRS GeoKey.")

        scale = tags["ModelPixelScaleTag"].value
        tiepoint = tags["ModelTiepointTag"].value
        if len(scale) < 2 or len(tiepoint) < 6:
            raise ValueError(f"{path} has incomplete pixel scale or tiepoint tags.")
        sx, sy = float(scale[0]), float(scale[1])
        if sx <= 0 or sy <= 0:
            raise ValueError(f"{path} has an invalid pixel scale.")
        i, j, _, x, y, _ = (float(value) for value in tiepoint[:6])
        x_origin = x - i * sx
        y_origin = y + j * sy
        if raster_type == 2:
            x_origin -= sx / 2.0
            y_origin += sy / 2.0
        if "GDAL_NODATA" in tags:
            nodata_value = tags["GDAL_NODATA"].value
            if isinstance(nodata_value, bytes):
                nodata_value = nodata_value.decode("ascii")
            nodata = float(str(nodata_value).rstrip("\x00"))
        else:
            nodata = float("nan")
        return RasterMetadata(
            crs_epsg=int(crs_epsg),
            transform=(sx, 0.0, x_origin, 0.0, -sy, y_origin),
            nodata=nodata,
            shape=tuple(page.shape),
        )


def validate_geotiff(
    path: Path,
    expected: RasterMetadata,
    *,
    transform_tolerance: float = 1e-9,
) -> np.ndarray:
    """Check embedded metadata and return the source pixel array."""
    actual = read_geotiff_metadata(path)
    if actual.crs_epsg != expected.crs_epsg:
        raise ValueError(f"{path}: EPSG:{actual.crs_epsg} != EPSG:{expected.crs_epsg}.")
    if actual.shape != expected.shape:
        raise ValueError(f"{path}: shape {actual.shape} != {expected.shape}.")
    if not np.isclose(actual.nodata, expected.nodata, rtol=0.0, atol=0.0):
        raise ValueError(f"{path}: nodata {actual.nodata} != {expected.nodata}.")
    if not np.allclose(actual.transform, expected.transform, rtol=0.0, atol=transform_tolerance):
        raise ValueError(f"{path}: transform {actual.transform} != {expected.transform}.")
    data = tifffile.imread(path)
    if data.shape != expected.shape or data.dtype != np.float32:
        raise ValueError(f"{path}: expected float32 data with shape {expected.shape}.")
    if np.any(~np.isfinite(data)):
        raise ValueError(f"{path} contains non-finite pixel values.")
    return data


def source_coverage_mask(
    shape: tuple[int, int],
    transform: Sequence[float],
    target_crs_epsg: int,
    source_bounds_wgs84: Iterable[tuple[float, float, float, float]],
) -> np.ndarray:
    """Mark target pixel centers covered by at least one verified source tile."""
    x_scale, _, x_origin, _, y_scale, y_origin = transform
    cols = np.arange(shape[1], dtype=np.float64)
    x = x_origin + (cols + 0.5) * x_scale
    transformer = Transformer.from_crs(target_crs_epsg, 4326, always_xy=True)
    supported = np.zeros(shape, dtype=bool)
    for row in range(shape[0]):
        y = y_origin + (row + 0.5) * y_scale
        lon, lat = transformer.transform(x, np.full(shape[1], y, dtype=np.float64))
        row_supported = np.zeros(shape[1], dtype=bool)
        for west, south, east, north in source_bounds_wgs84:
            row_supported |= (
                (lon >= west)
                & (lon < east)
                & (lat > south)
                & (lat <= north)
            )
        supported[row] = row_supported
    return supported


def valid_pixel_boundary_violations(
    data: np.ndarray,
    *,
    nodata: float,
    transform: Sequence[float],
    crs_epsg: int,
    boundary: BaseGeometry,
    row_chunk_size: int = 64,
) -> int:
    """Count valid pixel centers not covered by the supplied district polygon."""
    x_scale, _, x_origin, _, y_scale, y_origin = transform
    cols = np.arange(data.shape[1], dtype=np.float64)
    x = x_origin + (cols + 0.5) * x_scale
    transformer = Transformer.from_crs(crs_epsg, 4326, always_xy=True)
    violations = 0
    for first_row in range(0, data.shape[0], row_chunk_size):
        last_row = min(first_row + row_chunk_size, data.shape[0])
        block = data[first_row:last_row]
        rows, columns = np.nonzero(np.isfinite(block) & (block != nodata))
        if not len(rows):
            continue
        raster_rows = rows + first_row
        raster_x = x[columns]
        raster_y = y_origin + (raster_rows + 0.5) * y_scale
        lon, lat = transformer.transform(raster_x, raster_y)
        violations += int(np.count_nonzero(~covers(boundary, points(lon, lat))))
    return violations
