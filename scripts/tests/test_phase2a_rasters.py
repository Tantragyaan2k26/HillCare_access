from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

from scripts.phase2a_raster_utils import (
    RasterMetadata,
    read_geotiff_metadata,
    source_coverage_mask,
    valid_pixel_boundary_violations,
    validate_geotiff,
    write_geotiff,
)


def test_geotiff_embeds_crs_transform_nodata_and_dimensions(tmp_path):
    data = np.arange(12, dtype=np.float32).reshape(3, 4)
    transform = (30.0, 0.0, 500000.0, 0.0, -30.0, 3400000.0)
    path = tmp_path / "dem.tif"

    write_geotiff(
        path,
        data,
        crs_epsg=32644,
        transform=transform,
        nodata=-9999.0,
        description="unit test",
    )
    expected = RasterMetadata(32644, transform, -9999.0, data.shape)

    assert read_geotiff_metadata(path) == expected
    np.testing.assert_array_equal(validate_geotiff(path, expected), data)


def test_geotiff_validator_rejects_missing_georeferencing(tmp_path):
    path = tmp_path / "plain.tif"
    data = np.ones((2, 2), dtype=np.float32)
    import tifffile

    tifffile.imwrite(path, data, metadata=None)

    with pytest.raises(ValueError, match="missing GeoTIFF tags"):
        read_geotiff_metadata(path)


def test_pixel_is_point_source_metadata_maps_centers_to_area_affine(tmp_path):
    import tifffile

    path = tmp_path / "point-grid.tif"
    keys = (1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 2, 2048, 0, 1, 4326)
    tifffile.imwrite(
        path,
        np.ones((2, 2), dtype=np.float32),
        metadata=None,
        extratags=[
            (33550, "d", 3, (1.0, 1.0, 0.0), False),
            (33922, "d", 6, (0.0, 0.0, 0.0, 78.0, 31.0, 0.0), False),
            (34735, "H", len(keys), keys, False),
        ],
    )

    with pytest.raises(ValueError, match="PixelIsPoint"):
        read_geotiff_metadata(path, require_nodata=False)
    metadata = read_geotiff_metadata(path, require_nodata=False, allow_pixel_is_point=True)

    assert metadata.transform == (1.0, 0.0, 77.5, 0.0, -1.0, 31.5)


def test_source_coverage_masks_pixel_centers_east_of_raw_edge():
    data_transform = (0.5, 0.0, 80.0, 0.0, -0.5, 31.0)
    mask = source_coverage_mask(
        (2, 4),
        data_transform,
        4326,
        [(78.0, 29.0, 81.0, 31.0)],
    )

    np.testing.assert_array_equal(mask, [[True, True, False, False]] * 2)
    edge_transform = (0.5, 0.0, 80.5, 0.0, -0.5, 31.0)
    edge_mask = source_coverage_mask(
        (1, 2),
        edge_transform,
        4326,
        [(78.0, 29.0, 81.0, 31.0)],
    )
    np.testing.assert_array_equal(edge_mask, [[True, False]])


def test_valid_pixel_boundary_check_finds_outside_pixels():
    data = np.array([[1.0, 1.0], [1.0, -9999.0]], dtype=np.float32)
    transform = (1.0, 0.0, 0.0, 0.0, -1.0, 2.0)
    boundary = box(0.0, 0.0, 1.25, 2.0)

    violations = valid_pixel_boundary_violations(
        data,
        nodata=-9999.0,
        transform=transform,
        crs_epsg=4326,
        boundary=boundary,
    )

    assert violations == 1
