"""Unit tests for Dijkstra shortest path algorithms."""

import math
import numpy as np
import pytest
from hillcare_geoengine.cost_surface import CostGraph, TerrainModifiers
from hillcare_geoengine.dijkstra import multi_source_dijkstra, bounded_dijkstra
from hillcare_geoengine.raster import create_flat_dem, create_synthetic_himalayan_valley


def test_multi_source_nearest_facility_assignment():
    """Verify that multi-source Dijkstra correctly assigns each cell to its nearest facility."""
    rows, cols = 20, 20
    flat_dem = create_flat_dem(rows, cols)
    graph = CostGraph(flat_dem, cell_size_x=30.0, cell_size_y=30.0)

    # Source 1 at (0, 0), Source 2 at (19, 19)
    dist, nearest_id = multi_source_dijkstra(
        graph=graph,
        sources=[(0, 0), (19, 19)],
        source_ids=[101, 202],
    )

    # Near (0, 0) should be assigned to facility 101
    assert nearest_id[1, 1] == 101
    assert nearest_id[2, 2] == 101

    # Near (19, 19) should be assigned to facility 202
    assert nearest_id[18, 18] == 202
    assert nearest_id[17, 17] == 202

    # Distances at sources should be 0.0
    assert dist[0, 0] == 0.0
    assert dist[19, 19] == 0.0


def test_bounded_dijkstra_cutoff():
    """Verify that bounded Dijkstra strictly halts exploration beyond cutoff."""
    dem = create_synthetic_himalayan_valley(rows=40, cols=40)
    graph = CostGraph(dem, cell_size_x=30.0, cell_size_y=30.0)

    cutoff = 25.0  # 25 minutes
    reach_map = bounded_dijkstra(graph, source=(20, 20), cutoff_minutes=cutoff)

    assert len(reach_map) > 0
    # Center should have 0 time
    assert reach_map[(20, 20)] == 0.0

    # All reachable cells must be <= cutoff
    for coord, travel_time in reach_map.items():
        assert travel_time <= cutoff
