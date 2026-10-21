"""Candidate facility site generation, feasibility filtering, and scoring.

Generates candidate health facility locations and scores them based on newly covered
population, equity-weighted coverage, and mean travel time reductions.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from hillcare_geoengine.cost_surface import CostGraph
from hillcare_geoengine.dijkstra import bounded_dijkstra


@dataclass
class HabitationPoint:
    """Represents a settlement unit / habitation."""
    id: int
    name: str
    grid_coord: Tuple[int, int]  # (row, col)
    population: int
    sc_pct: float = 0.0
    st_pct: float = 0.0
    current_time_min: float = float("inf")
    is_underserved: bool = True


@dataclass
class CandidateSite:
    """A potential health facility location and its evaluated metrics."""
    id: int
    grid_coord: Tuple[int, int]  # (row, col)
    gain_pop: int = 0
    newly_covered_habitations: Set[int] = field(default_factory=set)
    reach_times: Dict[int, float] = field(default_factory=dict)  # hab_id -> new time
    mean_time_delta: float = 0.0
    equity_score: float = 0.0
    max_time_reduction: float = 0.0
    is_feasible: bool = True
    feasibility_notes: List[str] = field(default_factory=list)


def check_site_feasibility(
    graph: CostGraph,
    r: int,
    c: int,
    max_slope_deg: float = 25.0,
    check_radius_cells: int = 1,
    is_existing_settlement: bool = False,
) -> Tuple[bool, List[str]]:
    """Verify that a candidate site has buildable terrain and no hazards.

    Rules:
    1. Must not be inside an active river or seasonal landslide hazard cell.
    2. If not an established settlement, slope must be under max_slope_deg in surrounding area.
    """
    notes: List[str] = []
    if not graph.in_bounds(r, c):
        return False, ["out_of_bounds"]

    # Hazard checks
    if graph.modifiers.river_mask is not None and graph.modifiers.river_mask[r, c]:
        return False, ["located_in_river"]

    if graph.modifiers.disruption_mask is not None and graph.modifiers.disruption_mask[r, c]:
        return False, ["located_in_hazard_zone"]

    if is_existing_settlement:
        return True, ["feasible_settlement_site"]

    # Slope check within local radius
    max_grade = math.tan(math.radians(max_slope_deg))
    elev_center = float(graph.dem[r, c])

    for dr in range(-check_radius_cells, check_radius_cells + 1):
        for dc in range(-check_radius_cells, check_radius_cells + 1):
            if dr == 0 and dc == 0:
                continue
            nr = r + dr
            nc = c + dc
            if graph.in_bounds(nr, nc):
                h_dist = math.hypot(dr * graph.cell_size_y, dc * graph.cell_size_x)
                if h_dist > 0:
                    grade = abs(float(graph.dem[nr, nc]) - elev_center) / h_dist
                    if grade > max_grade:
                        notes.append(f"steep_slope_{math.degrees(math.atan(grade)):.1f}_deg")
                        return False, notes

    return True, ["feasible"]


def score_candidate(
    graph: CostGraph,
    candidate_coord: Tuple[int, int],
    candidate_id: int,
    habitations: List[HabitationPoint],
    threshold_min: float,
    is_hybrid: bool = False,
    initial_delay_minutes: float = 0.0,
    is_existing_settlement: bool = False,
) -> CandidateSite:
    """Score a candidate site by bounded Dijkstra outward reach.

    Computes:
    - gain_pop: newly covered population (people already <= threshold_min are EXCLUDED).
    - equity_score: population weighted by vulnerability (SC/ST representation).
    - mean_time_delta: average time savings across all underserved habitations.

    Args:
        graph: CostGraph (reversed for facilities).
        candidate_coord: (row, col) coordinates of the candidate.
        candidate_id: Unique candidate ID.
        habitations: List of habitations in the region.
        threshold_min: Maximum acceptable travel time (e.g. 30, 60, 90 min).
        is_hybrid: Whether hybrid vehicle mode applies.
        initial_delay_minutes: Wait penalty.
        is_existing_settlement: Whether this candidate is at an existing habitation.
    """
    is_feasible, notes = check_site_feasibility(
        graph,
        candidate_coord[0],
        candidate_coord[1],
        is_existing_settlement=is_existing_settlement,
    )
    candidate = CandidateSite(
        id=candidate_id,
        grid_coord=candidate_coord,
        is_feasible=is_feasible,
        feasibility_notes=notes,
    )

    if not is_feasible:
        return candidate

    # Run bounded Dijkstra up to threshold_min
    reach_map = bounded_dijkstra(
        graph=graph,
        source=candidate_coord,
        cutoff_minutes=threshold_min,
        is_hybrid=is_hybrid,
        initial_delay_minutes=initial_delay_minutes,
    )

    newly_covered_ids: Set[int] = set()
    total_gain_pop = 0
    total_equity_gain = 0.0
    total_time_reduction = 0.0
    max_red = 0.0

    for hab in habitations:
        hab_coord = hab.grid_coord
        if hab_coord in reach_map:
            new_time = reach_map[hab_coord]
            candidate.reach_times[hab.id] = new_time

            # Check if newly covered
            # Must currently be underserved (time > threshold_min) and reach <= threshold_min
            if hab.is_underserved and new_time <= threshold_min:
                newly_covered_ids.add(hab.id)
                total_gain_pop += hab.population

                # Equity multiplier: base weight 1.0 + (sc_pct + st_pct)
                equity_weight = 1.0 + ((hab.sc_pct + hab.st_pct) / 100.0)
                total_equity_gain += hab.population * equity_weight

            # Time reduction compared to current status
            if hab.current_time_min > new_time:
                reduction = hab.current_time_min - new_time
                total_time_reduction += reduction * hab.population
                if reduction > max_red:
                    max_red = reduction

    candidate.gain_pop = total_gain_pop
    candidate.newly_covered_habitations = newly_covered_ids
    candidate.equity_score = total_equity_gain
    candidate.max_time_reduction = max_red

    total_pop = sum(h.population for h in habitations)
    if total_pop > 0:
        candidate.mean_time_delta = total_time_reduction / total_pop

    return candidate
