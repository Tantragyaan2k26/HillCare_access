"""Sentinel-1 SAR processing and seasonal disruption detection (v1.1).

Processes synthetic or real Sentinel-1 C-band SAR backscatter (VV/VH polarization)
to detect monsoon flooding, river swelling, and landslide scars through dense monsoon clouds.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
import numpy as np


def compute_rtc_backscatter_db(
    raw_intensity: np.ndarray,
    noise_floor: float = 1e-4,
) -> np.ndarray:
    """Convert radiometric terrain-corrected (RTC) linear intensity to decibels (dB).

    Formula: sigma0_dB = 10 * log10(max(intensity, noise_floor))
    """
    clipped = np.maximum(raw_intensity, noise_floor)
    return 10.0 * np.log10(clipped)


def apply_lee_speckle_filter(
    sar_db: np.ndarray,
    window_size: int = 5,
    damping_factor: float = 1.0,
) -> np.ndarray:
    """Apply Lee speckle filter on SAR backscatter raster."""
    from scipy.ndimage import uniform_filter
    mean = uniform_filter(sar_db, size=window_size)
    mean_sq = uniform_filter(sar_db ** 2, size=window_size)
    var = np.maximum(0.0, mean_sq - mean ** 2)

    # Local noise estimate
    overall_var = np.var(sar_db)
    weight = var / (var + (overall_var / damping_factor) + 1e-6)
    filtered = mean + weight * (sar_db - mean)
    return filtered.astype(np.float32)


def detect_sar_monsoon_disruptions(
    dry_season_sar: np.ndarray,
    monsoon_sar: np.ndarray,
    slope_raster: np.ndarray,
    change_threshold_db: float = -4.5,
    high_slope_threshold_deg: float = 25.0,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Detect seasonal disruptions (landslides and flooded valley segments) using SAR change detection.

    Sentinel-1 radar penetrates clouds during monsoon.
    - Large negative change in backscatter on steep slopes indicates landslide debris flow or soil loss.
    - Specular water reflection (very low backscatter < -18 dB) in valley bottoms indicates river expansion/flooding.

    Returns:
        (disruption_mask, metrics_dict):
        - disruption_mask: 2D boolean mask where True = blocked cell during monsoon.
        - metrics_dict: summary of disrupted area and severity.
    """
    diff_db = monsoon_sar - dry_season_sar

    # 1. Landslide detection on steep slopes: significant backscatter change
    landslide_mask = (diff_db < change_threshold_db) & (slope_raster > high_slope_threshold_deg)

    # 2. Water / flooding mask: specular reflection brings monsoon backscatter below -18 dB
    water_flood_mask = monsoon_sar < -18.0

    combined_disruption = landslide_mask | water_flood_mask

    disrupted_cells = int(np.sum(combined_disruption))
    total_cells = int(combined_disruption.size)
    disrupted_pct = (disrupted_cells / total_cells) * 100.0

    metrics = {
        "disrupted_cell_count": disrupted_cells,
        "disrupted_area_pct": round(disrupted_pct, 2),
        "mean_sar_backscatter_diff_db": round(float(np.mean(diff_db)), 2),
        "landslide_trigger_count": int(np.sum(landslide_mask)),
        "flood_expansion_cell_count": int(np.sum(water_flood_mask)),
    }

    return combined_disruption, metrics
