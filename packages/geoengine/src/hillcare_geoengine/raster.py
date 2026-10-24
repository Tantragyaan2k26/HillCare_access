"""Raster generation, synthetic terrain benchmarks, and raster utilities.

Provides synthetic test terrains for analytical verification (flat, 10% slope,
symmetric ridge, river barrier) and real-world DEM utilities.
"""

from __future__ import annotations

import numpy as np


def create_flat_dem(rows: int, cols: int, elevation: float = 1000.0) -> np.ndarray:
    """Create a flat terrain DEM with constant elevation."""
    return np.full((rows, cols), elevation, dtype=np.float32)


def create_constant_slope_dem(
    rows: int,
    cols: int,
    base_elevation: float = 1000.0,
    cell_size_y: float = 30.0,
    slope: float = 0.10,  # 10% uphill in row direction
) -> np.ndarray:
    """Create a constant slope DEM.

    Slope = dz / (dy * rows). Moving from row 0 down increases elevation by slope * dy per cell.
    """
    dem = np.zeros((rows, cols), dtype=np.float32)
    for r in range(rows):
        dem[r, :] = base_elevation + (r * cell_size_y * slope)
    return dem


def create_symmetric_ridge_dem(
    rows: int,
    cols: int,
    base_elevation: float = 1000.0,
    peak_elevation: float = 1500.0,
    ridge_col: int | None = None,
    cell_size_x: float = 30.0,
) -> np.ndarray:
    """Create a symmetric ridge running north-south with peak at ridge_col."""
    if ridge_col is None:
        ridge_col = cols // 2
    dem = np.zeros((rows, cols), dtype=np.float32)
    max_dist = max(ridge_col, cols - 1 - ridge_col) * cell_size_x
    elev_diff = peak_elevation - base_elevation

    for c in range(cols):
        dist_from_ridge = abs(c - ridge_col) * cell_size_x
        elev = peak_elevation - (elev_diff * (dist_from_ridge / max_dist))
        dem[:, c] = elev
    return dem


def create_synthetic_himalayan_valley(
    rows: int = 100,
    cols: int = 100,
    cell_size: float = 30.0,
    base_elevation: float = 800.0,
    max_elevation: float = 2800.0,
) -> np.ndarray:
    """Create a realistic synthetic Himalayan valley terrain with ridges, valleys, and gorges."""
    x = np.linspace(0, 10, cols)
    y = np.linspace(0, 10, rows)
    xx, yy = np.meshgrid(x, y)

    # Multi-frequency sinusoidal terrain with main river gorge and intersecting spurs
    z = (
        0.5 * np.sin(0.7 * xx) * np.cos(0.5 * yy)
        + 0.3 * np.cos(1.2 * xx + 0.4 * yy)
        + 0.2 * np.sin(2.5 * xx) * np.sin(2.0 * yy)
    )
    # Normalize to [0, 1]
    z_norm = (z - z.min()) / (z.max() - z.min())
    dem = base_elevation + z_norm * (max_elevation - base_elevation)
    return dem.astype(np.float32)


def sample_raster_min_at_point(
    raster: np.ndarray,
    row: int,
    col: int,
    footprint_radius: int = 1,
) -> float:
    """Sample minimum raster value over a habitation footprint radius."""
    rows, cols = raster.shape
    r_min = max(0, row - footprint_radius)
    r_max = min(rows, row + footprint_radius + 1)
    c_min = max(0, col - footprint_radius)
    c_max = min(cols, col + footprint_radius + 1)
    window = raster[r_min:r_max, c_min:c_max]
    return float(np.min(window))
