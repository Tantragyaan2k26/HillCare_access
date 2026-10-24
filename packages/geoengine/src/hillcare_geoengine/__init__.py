"""HillCare GeoEngine package.

Slope-adjusted walking-time access analysis and facility siting optimization.
"""

from hillcare_geoengine.candidates import (
    CandidateSite,
    HabitationPoint,
    check_site_feasibility,
    score_candidate,
)
from hillcare_geoengine.cost_surface import (
    KNIGHT_OFFSETS,
    NEIGHBOUR_OFFSETS_16,
    QUEEN_OFFSETS,
    CostGraph,
    TerrainModifiers,
)
from hillcare_geoengine.dijkstra import (
    bounded_dijkstra,
    multi_source_dijkstra,
)
from hillcare_geoengine.optimiser import (
    OptimizationResult,
    select_facilities_exact,
    select_facilities_greedy,
)
from hillcare_geoengine.raster import (
    create_constant_slope_dem,
    create_flat_dem,
    create_symmetric_ridge_dem,
    create_synthetic_himalayan_valley,
    sample_raster_min_at_point,
)
from hillcare_geoengine.tobler import (
    DEFAULT_CALIBRATION,
    edge_time_hours,
    edge_time_minutes,
    tobler_speed_kmh,
)

__all__ = [
    "DEFAULT_CALIBRATION",
    "KNIGHT_OFFSETS",
    "NEIGHBOUR_OFFSETS_16",
    "QUEEN_OFFSETS",
    "CandidateSite",
    "CostGraph",
    "HabitationPoint",
    "OptimizationResult",
    "TerrainModifiers",
    "bounded_dijkstra",
    "check_site_feasibility",
    "create_constant_slope_dem",
    "create_flat_dem",
    "create_symmetric_ridge_dem",
    "create_synthetic_himalayan_valley",
    "edge_time_hours",
    "edge_time_minutes",
    "multi_source_dijkstra",
    "sample_raster_min_at_point",
    "score_candidate",
    "select_facilities_exact",
    "select_facilities_greedy",
    "tobler_speed_kmh",
]
