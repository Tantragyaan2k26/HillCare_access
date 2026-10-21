"""Unit tests for Tobler's Hiking Function and modifiers."""

import math
import pytest
from hillcare_geoengine.tobler import (
    DEFAULT_CALIBRATION,
    MIN_SPEED_KMH,
    MAX_SPEED_KMH,
    tobler_speed_kmh,
    edge_time_hours,
    edge_time_minutes,
)


def test_tobler_speed_extremes():
    """Test behavior at extreme slopes, gentle downhill, and vertical limits."""
    # Peak speed at S = -0.05
    peak_speed = tobler_speed_kmh(-0.05)
    assert math.isclose(peak_speed, 6.0, rel_tol=1e-5)

    # Any deviation from -0.05 must have lower speed
    assert tobler_speed_kmh(0.0) < peak_speed
    assert tobler_speed_kmh(-0.10) < peak_speed
    assert tobler_speed_kmh(0.30) < tobler_speed_kmh(0.10)

    # Steep cliff: clamped to MIN_SPEED_KMH
    cliff_speed = tobler_speed_kmh(5.0)  # 500% slope
    assert cliff_speed >= MIN_SPEED_KMH


def test_tobler_modifiers():
    """Test calibration, carried patient, and trail speed multipliers."""
    base_speed = tobler_speed_kmh(0.0, calibration=1.0)

    # Calibration factor
    cal_low = tobler_speed_kmh(0.0, calibration=0.8)
    cal_high = tobler_speed_kmh(0.0, calibration=1.2)
    assert math.isclose(cal_low, base_speed * 0.8, rel_tol=1e-5)
    assert math.isclose(cal_high, base_speed * 1.2, rel_tol=1e-5)

    # Carried patient multiplier (2.0x time -> 0.5x speed)
    carried_speed = tobler_speed_kmh(0.0, emergency_multiplier=2.0)
    assert math.isclose(carried_speed, base_speed / 2.0, rel_tol=1e-5)

    # Trail speed multiplier (1.25x boost)
    trail_speed = tobler_speed_kmh(0.0, trail_speed_multiplier=1.25)
    assert math.isclose(trail_speed, base_speed * 1.25, rel_tol=1e-5)


def test_edge_time_calculations():
    """Test 3D distance and travel time conversions."""
    # Zero distance
    assert edge_time_hours(0.0, 0.0) == 0.0
    assert edge_time_minutes(0.0, 0.0) == 0.0

    # Impassable barrier
    assert math.isinf(edge_time_hours(30.0, 5.0, barrier=True))
    assert math.isinf(edge_time_minutes(30.0, 5.0, barrier=True))

    # Friction penalty
    t_normal = edge_time_hours(100.0, 0.0, friction_penalty=1.0)
    t_friction = edge_time_hours(100.0, 0.0, friction_penalty=1.5)
    assert math.isclose(t_friction, t_normal * 1.5, rel_tol=1e-5)
