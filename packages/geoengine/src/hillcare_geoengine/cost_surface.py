"""Cost surface and 16-neighbour terrain graph for slope-adjusted hiking.

Constructs 16-neighbour connectivity graphs (8 Queen + 8 Knight moves) over DEM rasters
with directional slopes, surface modifiers (trails, roads, rivers, bridges),
and graph reversal for efficient multi-source reverse Dijkstra.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from hillcare_geoengine.tobler import (
    DEFAULT_CALIBRATION,
    edge_time_minutes,
    tobler_speed_kmh,
)

# 16-neighbour moves: (delta_row, delta_col)
QUEEN_OFFSETS: List[Tuple[int, int]] = [
    (-1, 0), (1, 0), (0, -1), (0, 1),      # orthogonal
    (-1, -1), (-1, 1), (1, -1), (1, 1),     # diagonal
]

KNIGHT_OFFSETS: List[Tuple[int, int]] = [
    (-2, -1), (-2, 1), (2, -1), (2, 1),
    (-1, -2), (-1, 2), (1, -2), (1, 2),
]

NEIGHBOUR_OFFSETS_16: List[Tuple[int, int]] = QUEEN_OFFSETS + KNIGHT_OFFSETS


@dataclass
class TerrainModifiers:
    """Terrain overlays that modify or restrict movement."""
    # 2D boolean mask: True where footpaths/trails exist (1.25x speed multiplier)
    trail_mask: Optional[np.ndarray] = None
    trail_speed_multiplier: float = 1.25

    # 2D boolean mask: True where motorable roads exist (hybrid mode)
    road_mask: Optional[np.ndarray] = None
    road_vehicle_speed_kmh: float = 20.0

    # 2D boolean mask: True where river is present
    river_mask: Optional[np.ndarray] = None

    # 2D boolean mask: True where bridges/fords exist across rivers
    bridge_mask: Optional[np.ndarray] = None

    # 2D boolean mask: True where seasonal/landslide disruptions block passage
    disruption_mask: Optional[np.ndarray] = None

    # 2D float array: Multipliers for land cover / hazard friction (>= 1.0)
    friction_raster: Optional[np.ndarray] = None


@dataclass
class CostGraph:
    """16-neighbour directional cost graph constructed on a DEM raster."""
    dem: np.ndarray  # 2D array of elevations (meters)
    cell_size_x: float  # horizontal resolution in meters (e.g. 30.0)
    cell_size_y: float  # vertical resolution in meters (e.g. 30.0)
    modifiers: TerrainModifiers = field(default_factory=TerrainModifiers)
    calibration: float = DEFAULT_CALIBRATION
    emergency_multiplier: float = 1.0
    reversed_for_facilities: bool = True

    @property
    def shape(self) -> Tuple[int, int]:
        return self.dem.shape

    @property
    def rows(self) -> int:
        return self.dem.shape[0]

    @property
    def cols(self) -> int:
        return self.dem.shape[1]

    def in_bounds(self, r: int, c: int) -> bool:
        """Check if grid coordinates are within the DEM bounding box."""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def _get_traversed_cells(self, r1: int, c1: int, r2: int, c2: int) -> List[Tuple[int, int]]:
        """Return all grid cells traversed along the line segment from (r1, c1) to (r2, c2)."""
        dr = r2 - r1
        dc = c2 - c1
        cells: Set[Tuple[int, int]] = {(r1, c1), (r2, c2)}

        # For Knight's moves (e.g. 2 cells in one direction, 1 in the other)
        # add intermediate cells to prevent jumping over 1-cell barriers
        if abs(dr) == 1 and abs(dc) == 2:
            step_c = 1 if dc > 0 else -1
            cells.add((r1, c1 + step_c))
            cells.add((r2, c1 + step_c))
        elif abs(dr) == 2 and abs(dc) == 1:
            step_r = 1 if dr > 0 else -1
            cells.add((r1 + step_r, c1))
            cells.add((r1 + step_r, c2))

        return list(cells)

    def get_edge_time(
        self,
        r1: int,
        c1: int,
        r2: int,
        c2: int,
        is_hybrid: bool = False,
    ) -> float:
        """Compute traversal time in minutes from (r1, c1) to (r2, c2).

        If `reversed_for_facilities` is True, this returns the cost of the *forward*
        movement from (r2, c2) to (r1, c1), which is what Dijkstra exploring outward
        from a facility needs in order to accumulate Habitation -> Facility travel time.
        """
        if not (self.in_bounds(r1, c1) and self.in_bounds(r2, c2)):
            return float("inf")

        # In reversed mode: moving from r1,c1 to r2,c2 explores backwards along the edge r2,c2 -> r1,c1.
        # So the forward traversal was actually from (r2, c2) -> (r1, c1).
        if self.reversed_for_facilities:
            src_r, src_c = r2, c2
            dst_r, dst_c = r1, c1
        else:
            src_r, src_c = r1, c1
            dst_r, dst_c = r2, c2

        # Get all cells traversed along the edge (start, intermediate, end)
        cells_traversed = self._get_traversed_cells(src_r, src_c, dst_r, dst_c)

        # Check barriers: river without bridge
        if self.modifiers.river_mask is not None:
            for cr, cc in cells_traversed:
                if self.modifiers.river_mask[cr, cc]:
                    is_bridge = (
                        self.modifiers.bridge_mask is not None
                        and self.modifiers.bridge_mask[cr, cc]
                    )
                    if not is_bridge:
                        return float("inf")

        # Check seasonal landslide/disruption barriers
        if self.modifiers.disruption_mask is not None:
            for cr, cc in cells_traversed:
                if self.modifiers.disruption_mask[cr, cc]:
                    return float("inf")

        # Elevation diff
        z1 = float(self.dem[src_r, src_c])
        z2 = float(self.dem[dst_r, dst_c])
        dz = z2 - z1

        # Horizontal distance
        dr = dst_r - src_r
        dc = dst_c - src_c
        dx = dc * self.cell_size_x
        dy = dr * self.cell_size_y
        h_dist = math.hypot(dx, dy)
        if h_dist <= 0:
            return 0.0

        # Check if road (in hybrid mode, roads allow vehicle speed)
        if is_hybrid and self.modifiers.road_mask is not None:
            if self.modifiers.road_mask[src_r, src_c] and self.modifiers.road_mask[dst_r, dst_c]:
                # Motorable road travel
                speed = self.modifiers.road_vehicle_speed_kmh
                dist_km = math.hypot(h_dist, dz) / 1000.0
                return (dist_km / speed) * 60.0

        # Check trail boost
        trail_mult = 1.0
        if self.modifiers.trail_mask is not None:
            if self.modifiers.trail_mask[dst_r, dst_c]:
                trail_mult = self.modifiers.trail_speed_multiplier

        # Surface friction
        friction = 1.0
        if self.modifiers.friction_raster is not None:
            friction = float(self.modifiers.friction_raster[dst_r, dst_c])

        return edge_time_minutes(
            horizontal_dist_m=h_dist,
            dz_m=dz,
            calibration=self.calibration,
            emergency_multiplier=self.emergency_multiplier,
            trail_speed_multiplier=trail_mult,
            barrier=False,
            friction_penalty=friction,
        )

    def get_neighbours(
        self,
        r: int,
        c: int,
        is_hybrid: bool = False,
    ) -> List[Tuple[int, int, float]]:
        """Return list of (nr, nc, cost_minutes) for all valid 16-neighbours."""
        res: List[Tuple[int, int, float]] = []
        for dr, dc in NEIGHBOUR_OFFSETS_16:
            nr = r + dr
            nc = c + dc
            if self.in_bounds(nr, nc):
                cost = self.get_edge_time(r, c, nr, nc, is_hybrid=is_hybrid)
                if not math.isinf(cost):
                    res.append((nr, nc, cost))
        return res
