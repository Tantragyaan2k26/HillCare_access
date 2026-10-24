"""Multi-source and bounded Dijkstra shortest-path algorithms on terrain graphs.

Optimized for:
1. Multi-source Dijkstra from health facilities on reversed graph.
2. Bounded Dijkstra for localized candidate site evaluation.
"""

from __future__ import annotations

import heapq

import numpy as np

from hillcare_geoengine.cost_surface import CostGraph


def multi_source_dijkstra(
    graph: CostGraph,
    sources: list[tuple[int, int]],
    source_ids: list[int] | None = None,
    is_hybrid: bool = False,
    initial_delay_minutes: float = 0.0,
    max_time_minutes: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute travel time from all grid cells to the nearest source facility.

    Runs multi-source Dijkstra outward from the facility cells. On a reversed graph
    (graph.reversed_for_facilities=True), edge weights reflect habitation->facility travel times.

    Args:
        graph: CostGraph representing the terrain.
        sources: List of (row, col) coordinates of functional facilities.
        source_ids: List of integer identifiers corresponding to each source.
        is_hybrid: Whether to allow road vehicle speeds along road cells.
        initial_delay_minutes: Wait penalty (e.g. 20 min in hybrid mode).
        max_time_minutes: Optional upper threshold to truncate search.

    Returns:
        (travel_time_raster, nearest_source_id_raster):
        - travel_time_raster: 2D array of floats with minutes to nearest facility (inf if unreachable).
        - nearest_source_id_raster: 2D array of ints with ID of nearest facility (-1 if unreachable).
    """
    rows, cols = graph.shape
    dist = np.full((rows, cols), np.inf, dtype=np.float64)
    nearest_id = np.full((rows, cols), -1, dtype=np.int32)

    pq: list[tuple[float, int, int, int]] = []  # (time, r, c, src_id)

    if source_ids is None:
        source_ids = list(range(len(sources)))

    for i, (sr, sc) in enumerate(sources):
        if graph.in_bounds(sr, sc):
            start_time = initial_delay_minutes
            if start_time < dist[sr, sc]:
                dist[sr, sc] = start_time
                s_id = source_ids[i]
                nearest_id[sr, sc] = s_id
                heapq.heappush(pq, (start_time, sr, sc, s_id))

    while pq:
        d, r, c, s_id = heapq.heappop(pq)

        if d > dist[r, c]:
            continue

        if max_time_minutes is not None and d > max_time_minutes:
            continue

        for nr, nc, edge_cost in graph.get_neighbours(r, c, is_hybrid=is_hybrid):
            new_dist = d + edge_cost
            if max_time_minutes is not None and new_dist > max_time_minutes:
                continue

            if new_dist < dist[nr, nc]:
                dist[nr, nc] = new_dist
                nearest_id[nr, nc] = s_id
                heapq.heappush(pq, (new_dist, nr, nc, s_id))

    return dist, nearest_id


def bounded_dijkstra(
    graph: CostGraph,
    source: tuple[int, int],
    cutoff_minutes: float,
    is_hybrid: bool = False,
    initial_delay_minutes: float = 0.0,
) -> dict[tuple[int, int], float]:
    """Compute reachability from a single candidate point up to a cutoff threshold.

    Used by the candidate siting optimizer to find all habitations reachable
    within threshold T (e.g. 30, 60, 90 minutes).

    Args:
        graph: CostGraph representing the terrain.
        source: (row, col) grid coordinate of the candidate facility.
        cutoff_minutes: Maximum travel time to explore.
        is_hybrid: Whether hybrid vehicle mode applies.
        initial_delay_minutes: Starting delay (if any).

    Returns:
        Dict mapping (r, c) -> travel_time_minutes for all reachable cells <= cutoff.
    """
    sr, sc = source
    if not graph.in_bounds(sr, sc):
        return {}

    dist: dict[tuple[int, int], float] = {(sr, sc): initial_delay_minutes}
    pq: list[tuple[float, int, int]] = [(initial_delay_minutes, sr, sc)]

    while pq:
        d, r, c = heapq.heappop(pq)

        if d > dist.get((r, c), float("inf")):
            continue

        for nr, nc, edge_cost in graph.get_neighbours(r, c, is_hybrid=is_hybrid):
            new_dist = d + edge_cost
            if new_dist <= cutoff_minutes and new_dist < dist.get((nr, nc), float("inf")):
                dist[(nr, nc)] = new_dist
                heapq.heappush(pq, (new_dist, nr, nc))

    return dist
