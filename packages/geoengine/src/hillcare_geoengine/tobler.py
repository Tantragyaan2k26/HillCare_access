"""Tobler's Hiking Function and walking speed calculations.

Implements Waldo Tobler's empirical hiking formulation for slope-adjusted
walking speed and edge traversal times, including trail quality, calibration
factors, and emergency/carried-patient modifiers.
"""

from __future__ import annotations

import math
from typing import Final

# Default calibration factor (1.0 = base; field adjustments typically range 0.8 to 1.2)
DEFAULT_CALIBRATION: Final[float] = 1.0

# Minimum speed floor (km/h) to prevent division by zero on near-vertical cliffs
MIN_SPEED_KMH: Final[float] = 0.01

# Maximum reasonable human walking/scrambling speed limit (km/h)
MAX_SPEED_KMH: Final[float] = 15.0


def tobler_speed_kmh(
    slope: float,
    calibration: float = DEFAULT_CALIBRATION,
    emergency_multiplier: float = 1.0,
    trail_speed_multiplier: float = 1.0,
) -> float:
    """Calculate walking speed in km/h based on terrain slope.

    Tobler's formula:
        v = 6.0 * exp(-3.5 * |S + 0.05|) [km/h]
    where S is the rise over run (slope), signed in the direction of movement.
    Peak velocity occurs at S = -0.05 (~5.037 km/h, gentle downhill).

    Args:
        slope: Signed slope (dz / horizontal_dx). Positive = uphill, Negative = downhill.
        calibration: Empirical scaling factor (default 1.0, low=0.8, high=1.2).
        emergency_multiplier: Factor by which walking time increases when carrying
            a patient or in emergency evacuation (default 1.0, carried=2.0).
            Correspondingly, speed is divided by this factor.
        trail_speed_multiplier: Speed boost on prepared trails/paths (default 1.0; 1.25 on paths).

    Returns:
        Walking speed in km/h.
    """
    base_speed = 6.0 * math.exp(-3.5 * abs(slope + 0.05))
    adjusted_speed = (base_speed * calibration * trail_speed_multiplier) / emergency_multiplier
    return max(MIN_SPEED_KMH, min(MAX_SPEED_KMH, adjusted_speed))


def edge_time_hours(
    horizontal_dist_m: float,
    dz_m: float,
    calibration: float = DEFAULT_CALIBRATION,
    emergency_multiplier: float = 1.0,
    trail_speed_multiplier: float = 1.0,
    barrier: bool = False,
    friction_penalty: float = 1.0,
) -> float:
    """Calculate traversal time in hours along an edge.

    Uses 3D Euclidean distance sqrt(dx^2 + dy^2 + dz^2).

    Args:
        horizontal_dist_m: Horizontal distance in meters (must be > 0).
        dz_m: Signed height difference in meters (target_elevation - source_elevation).
        calibration: Tobler calibration factor.
        emergency_multiplier: Carried patient modifier (e.g. 2.0).
        trail_speed_multiplier: Multiplier for trail surface.
        barrier: If True (e.g. unbridged river cell), edge is impassable (inf time).
        friction_penalty: Surface penalty (e.g. dense forest, snow, debris; default 1.0).

    Returns:
        Travel time in hours, or float('inf') if impassable.
    """
    if barrier:
        return float("inf")
    if horizontal_dist_m <= 0:
        return 0.0

    slope = dz_m / horizontal_dist_m
    speed_kmh = tobler_speed_kmh(
        slope=slope,
        calibration=calibration,
        emergency_multiplier=emergency_multiplier,
        trail_speed_multiplier=trail_speed_multiplier,
    )
    dist_3d_km = math.hypot(horizontal_dist_m, dz_m) / 1000.0
    return (dist_3d_km / speed_kmh) * friction_penalty


def edge_time_minutes(
    horizontal_dist_m: float,
    dz_m: float,
    calibration: float = DEFAULT_CALIBRATION,
    emergency_multiplier: float = 1.0,
    trail_speed_multiplier: float = 1.0,
    barrier: bool = False,
    friction_penalty: float = 1.0,
) -> float:
    """Calculate traversal time in minutes along an edge."""
    return edge_time_hours(
        horizontal_dist_m=horizontal_dist_m,
        dz_m=dz_m,
        calibration=calibration,
        emergency_multiplier=emergency_multiplier,
        trail_speed_multiplier=trail_speed_multiplier,
        barrier=barrier,
        friction_penalty=friction_penalty,
    ) * 60.0
