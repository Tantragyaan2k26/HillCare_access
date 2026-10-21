"""HillCare GeoEngine package.

Slope-adjusted walking-time access analysis and facility siting optimization.
"""

from hillcare_geoengine.tobler import (
    DEFAULT_CALIBRATION,
    tobler_speed_kmh,
    edge_time_hours,
    edge_time_minutes,
)
from hillcare_geoengine.cost_surface import (
    CostGraph,
    TerrainModifiers,
    QUEEN_OFFSETS,
    KNIGHT_OFFSETS,
    NEIGHBOUR_OFFSETS_16,
)
from hillcare_geoengine.dijkstra import (
    multi_source_dijkstra,
    bounded_dijkstra,
)
from hillcare_geoengine.candidates import (
    HabitationPoint,
    CandidateSite,
    check_site_feasibility,
    score_candidate,
)
from hillcare_geoengine.optimiser import (
    OptimizationResult,
    select_facilities_greedy,
    select_facilities_exact,
)
from hillcare_geoengine.raster import (
    create_flat_dem,
    create_constant_slope_dem,
    create_symmetric_ridge_dem,
    create_synthetic_himalayan_valley,
    sample_raster_min_at_point,
)

__all__ = [
    "DEFAULT_CALIBRATION",
    "tobler_speed_kmh",
    "edge_time_hours",
    "edge_time_minutes",
    "CostGraph",
    "TerrainModifiers",
    "QUEEN_OFFSETS",
    "KNIGHT_OFFSETS",
    "NEIGHBOUR_OFFSETS_16",
    "multi_source_dijkstra",
    "bounded_dijkstra",
    "HabitationPoint",
    "CandidateSite",
    "check_site_feasibility",
    "score_candidate",
    "OptimizationResult",
    "select_facilities_greedy",
    "select_facilities_exact",
    "create_flat_dem",
    "create_constant_slope_dem",
    "create_symmetric_ridge_dem",
    "create_synthetic_himalayan_valley",
    "sample_raster_min_at_point",
]
