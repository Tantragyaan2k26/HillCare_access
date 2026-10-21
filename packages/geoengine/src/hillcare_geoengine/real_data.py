"""Read-only loader for the project's real district datasets.

Loading these records does not run accessibility calculations or alter the
existing synthetic pipeline path. WorldPop density is intentionally excluded:
it is not a per-habitation population count.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import tifffile
from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as transform_geometry


DISTRICTS = ("Chamoli", "Pithoragarh", "Rudraprayag")
VECTOR_CRS = CRS.from_epsg(4326)
DEM_NODATA = -9999.0


@dataclass(frozen=True)
class RealRaster:
    """Raster pixels and the geospatial metadata required to interpret them."""

    data: np.ndarray
    valid_mask: np.ndarray
    crs: CRS
    transform: tuple[float, float, float, float, float, float]
    resolution: tuple[float, float]
    nodata: float
    path: Path


@dataclass(frozen=True)
class RealFeature:
    """A source feature, preserving its source geometry, ID, and properties."""

    kind: str
    source_id: Any
    district: str
    properties: Mapping[str, Any]
    source_geometry: BaseGeometry | None
    projected_geometry: BaseGeometry | None
    source_crs: CRS
    projected_crs: CRS
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataReview:
    """An input record requiring human review; the record is retained."""

    kind: str
    source_id: Any
    district: str
    reason: str
    feature: RealFeature
    distance_to_district_m: float | None = None


@dataclass(frozen=True)
class RealDistrictData:
    """Loaded real inputs for one district; no travel-time results are computed."""

    district: str
    dem: RealRaster
    boundary: RealFeature
    habitations: tuple[RealFeature, ...]
    facilities: tuple[RealFeature, ...]
    roads: tuple[RealFeature, ...]
    review_records: tuple[DataReview, ...] = field(default_factory=tuple)


def _read_epsg_geotiff(path: Path) -> tuple[CRS, tuple[float, float, float, float, float, float], float]:
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        tags = page.tags
        required = ("GeoKeyDirectoryTag", "ModelPixelScaleTag", "ModelTiepointTag", "GDAL_NODATA")
        missing = [tag for tag in required if tag not in tags]
        if missing:
            raise ValueError(f"{path} lacks required embedded tags: {', '.join(missing)}.")

        keys = tags["GeoKeyDirectoryTag"].value
        if len(keys) < 4 or keys[:3] != (1, 1, 0) or len(keys) != 4 + keys[3] * 4:
            raise ValueError(f"{path} has an invalid GeoKeyDirectory.")
        key_values = {
            keys[offset]: keys[offset + 3]
            for offset in range(4, len(keys), 4)
        }
        model_type = key_values.get(1024)
        if model_type not in (1, 2) or key_values.get(1025) != 1:
            raise ValueError(f"{path} must declare a PixelIsArea projected or geographic CRS.")
        epsg = key_values.get(3072 if model_type == 1 else 2048)
        if epsg is None:
            raise ValueError(f"{path} has no EPSG CRS key.")
        crs = CRS.from_epsg(int(epsg))

        scale = tags["ModelPixelScaleTag"].value
        tiepoint = tags["ModelTiepointTag"].value
        if len(scale) < 2 or len(tiepoint) < 6:
            raise ValueError(f"{path} has incomplete pixel scale/tiepoint tags.")
        sx, sy = float(scale[0]), float(scale[1])
        i, j, _, x, y, _ = (float(value) for value in tiepoint[:6])
        if sx <= 0 or sy <= 0:
            raise ValueError(f"{path} has invalid pixel scales.")
        transform = (sx, 0.0, x - i * sx, 0.0, -sy, y + j * sy)
        nodata_value = tags["GDAL_NODATA"].value
        if isinstance(nodata_value, bytes):
            nodata_value = nodata_value.decode("ascii")
        nodata = float(str(nodata_value).rstrip("\x00"))
        return crs, transform, nodata


def _load_dem(data_dir: Path, district: str) -> RealRaster:
    raster_path = data_dir / "processed_phase2a" / f"dem_{district.lower()}_utm44n.tif"
    sidecar_path = data_dir / "processed" / f"dem_{district.lower()}_utm44n.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if sidecar.get("district") != district:
        raise ValueError(f"{sidecar_path} does not declare district {district}.")

    crs, transform, nodata = _read_epsg_geotiff(raster_path)
    sidecar_crs = CRS.from_user_input(sidecar["crs"])
    sidecar_transform = tuple(float(value) for value in sidecar["transform"])
    if crs != sidecar_crs:
        raise ValueError(f"{raster_path} embedded CRS disagrees with its verified sidecar.")
    if not np.allclose(transform, sidecar_transform, rtol=0.0, atol=1e-9):
        raise ValueError(f"{raster_path} embedded transform disagrees with its verified sidecar.")
    if not math.isclose(nodata, float(sidecar["nodata"]), rel_tol=0.0, abs_tol=0.0):
        raise ValueError(f"{raster_path} embedded nodata disagrees with its verified sidecar.")

    data = tifffile.memmap(raster_path)
    if data.ndim != 2 or data.dtype != np.float32 or tuple(data.shape) != tuple(sidecar["shape"]):
        raise ValueError(f"{raster_path} dimensions or dtype disagree with the verified metadata.")
    valid_mask = np.isfinite(data) & (data != nodata)
    return RealRaster(
        data=data,
        valid_mask=valid_mask,
        crs=crs,
        transform=transform,
        resolution=(abs(transform[0]), abs(transform[4])),
        nodata=nodata,
        path=raster_path,
    )


def _geojson_crs(document: Mapping[str, Any], path: Path) -> CRS:
    declaration = document.get("crs")
    if not isinstance(declaration, Mapping):
        raise ValueError(f"{path} does not explicitly declare a CRS.")
    properties = declaration.get("properties")
    if not isinstance(properties, Mapping) or not isinstance(properties.get("name"), str):
        raise ValueError(f"{path} has an unsupported GeoJSON CRS declaration.")
    crs_name = properties["name"]
    crs = CRS.from_user_input(crs_name)
    if crs.to_epsg() != 4326 and crs.to_authority() != ("OGC", "CRS84"):
        raise ValueError(f"{path} must declare the verified CRS84/EPSG:4326 coordinates.")
    return crs


def _load_geojson(path: Path) -> tuple[CRS, list[Mapping[str, Any]]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
        raise ValueError(f"{path} is not a GeoJSON FeatureCollection.")
    return _geojson_crs(document, path), document["features"]


def _source_id(kind: str, properties: Mapping[str, Any]) -> Any:
    source_keys = {
        "habitation": ("id",),
        "facility": ("nic_source_id", "pmgsy_source_id", "facility_id", "id"),
        "road": ("er_id",),
        "boundary": ("lgd_code",),
    }
    return next((properties[key] for key in source_keys[kind] if properties.get(key) is not None), None)


def _make_feature(
    kind: str,
    feature: Mapping[str, Any],
    source_crs: CRS,
    target_crs: CRS,
    transformer: Transformer,
) -> RealFeature:
    properties = dict(feature.get("properties") or {})
    district = properties.get("district") or properties.get("district_name") or ""
    source_geometry: BaseGeometry | None = None
    projected_geometry: BaseGeometry | None = None
    issues: list[str] = []

    try:
        geometry_data = feature.get("geometry")
        if not isinstance(geometry_data, Mapping):
            raise ValueError("geometry is missing")
        source_geometry = shape(geometry_data)
        if source_geometry.is_empty:
            issues.append("geometry is empty")
        elif not source_geometry.is_valid:
            issues.append("geometry is invalid")
        elif any(not math.isfinite(value) for value in source_geometry.bounds):
            issues.append("geometry has non-finite coordinates")
        elif (
            source_geometry.bounds[0] < -180
            or source_geometry.bounds[2] > 180
            or source_geometry.bounds[1] < -90
            or source_geometry.bounds[3] > 90
        ):
            issues.append("geometry coordinates fall outside declared geographic CRS bounds")
        else:
            projected_geometry = transform_geometry(transformer.transform, source_geometry)
    except (TypeError, ValueError, KeyError) as exc:
        issues.append(f"geometry could not be parsed: {exc}")

    return RealFeature(
        kind=kind,
        source_id=_source_id(kind, properties),
        district=str(district),
        properties=properties,
        source_geometry=source_geometry,
        projected_geometry=projected_geometry,
        source_crs=source_crs,
        projected_crs=target_crs,
        issues=tuple(issues),
    )


def _feature_review(feature: RealFeature, boundary: RealFeature) -> DataReview | None:
    if feature.issues:
        return DataReview(
            kind=feature.kind,
            source_id=feature.source_id,
            district=feature.district,
            reason="; ".join(feature.issues),
            feature=feature,
        )
    if feature.kind != "habitation":
        return None
    assert feature.source_geometry is not None
    assert boundary.source_geometry is not None
    if boundary.source_geometry.covers(feature.source_geometry):
        return None
    assert feature.projected_geometry is not None
    assert boundary.projected_geometry is not None
    return DataReview(
        kind=feature.kind,
        source_id=feature.source_id,
        district=feature.district,
        reason="habitation point is outside its assigned district polygon",
        feature=feature,
        distance_to_district_m=boundary.projected_geometry.distance(feature.projected_geometry),
    )


def load_real_district_data(data_dir: Path, district: str) -> RealDistrictData:
    """Load real raster/vector inputs for one district without running analysis.

    Args:
        data_dir: Project ``data`` directory containing ``processed`` and
            ``processed_phase2a``.
        district: Exact pilot district name.

    The loader preserves every selected feature and its properties. Invalid
    geometries and out-of-boundary habitations are included in
    ``review_records`` rather than silently discarded or reassigned.
    """
    if district not in DISTRICTS:
        raise ValueError(f"Unknown pilot district: {district}.")
    data_dir = Path(data_dir)
    dem = _load_dem(data_dir, district)
    target_crs = dem.crs
    processed_dir = data_dir / "processed"

    boundary_crs, boundary_source = _load_geojson(processed_dir / "district_boundaries.geojson")
    boundary_districts = {
        (feature.get("properties") or {}).get("district_name")
        for feature in boundary_source
    }
    if boundary_districts != set(DISTRICTS):
        raise ValueError("District boundary dataset has missing or unexpected district assignments.")
    transformer = Transformer.from_crs(boundary_crs, target_crs, always_xy=True)
    boundaries = [
        _make_feature("boundary", feature, boundary_crs, target_crs, transformer)
        for feature in boundary_source
        if (feature.get("properties") or {}).get("district_name") == district
    ]
    if len(boundaries) != 1:
        raise ValueError(f"Expected exactly one boundary for {district}, found {len(boundaries)}.")
    boundary = boundaries[0]
    if boundary.issues or boundary.source_geometry is None or boundary.projected_geometry is None:
        raise ValueError(f"District boundary for {district} is invalid: {boundary.issues}.")

    inputs = (
        ("habitation", "habitations_target_districts.geojson"),
        ("facility", "facilities_target_districts.geojson"),
        ("road", "roads_target_districts.geojson"),
    )
    loaded: dict[str, tuple[RealFeature, ...]] = {}
    reviews: list[DataReview] = []
    for kind, filename in inputs:
        source_crs, source_features = _load_geojson(processed_dir / filename)
        assignments = [
            (feature.get("properties") or {}).get("district")
            for feature in source_features
        ]
        if any(assignment not in DISTRICTS for assignment in assignments):
            raise ValueError(f"{filename} contains missing or unexpected district assignments.")
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        records = tuple(
            _make_feature(kind, feature, source_crs, target_crs, transformer)
            for feature in source_features
            if (feature.get("properties") or {}).get("district") == district
        )
        if any(not record.district for record in records):
            raise ValueError(f"{filename} contains a selected record without a district assignment.")
        loaded[kind] = records
        for record in records:
            review = _feature_review(record, boundary)
            if review is not None:
                reviews.append(review)

    return RealDistrictData(
        district=district,
        dem=dem,
        boundary=boundary,
        habitations=loaded["habitation"],
        facilities=loaded["facility"],
        roads=loaded["road"],
        review_records=tuple(reviews),
    )
