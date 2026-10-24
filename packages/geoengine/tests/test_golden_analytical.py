"""Analytical and golden tests for HillCare GeoEngine.

Directly tests the analytical ground truths specified in Section 15 of the System Design Document:
1. Flat plane: time = distance / 5 km/h.
2. Constant 10% uphill: matches closed-form Tobler speed.
3. Symmetric ridge: asymmetry check (uphill time != downhill time).
4. River barrier: cell cost infinite without bridge, accessible with bridge.
5. Monotonicity & property checks: adding a facility never increases travel time.
6. Coverage exclusion: newly covered counts strictly exclude already-served habitations.
7. Greedy vs exact solver: matches on small candidate instances.
"""

import math

import numpy as np
from hillcare_geoengine.candidates import (
    CandidateSite,
    HabitationPoint,
    score_candidate,
)
from hillcare_geoengine.cost_surface import CostGraph, TerrainModifiers
from hillcare_geoengine.dijkstra import multi_source_dijkstra
from hillcare_geoengine.optimiser import (
    select_facilities_exact,
    select_facilities_greedy,
)
from hillcare_geoengine.raster import (
    create_constant_slope_dem,
    create_flat_dem,
    create_symmetric_ridge_dem,
)
from hillcare_geoengine.tobler import (
    edge_time_minutes,
    tobler_speed_kmh,
)


class TestGoldenAnalyticalRasters:
    """Golden analytical tests matching closed-form solutions."""

    def test_golden_flat_plane_speed_and_time(self):
        """Golden Test 1: Flat plane speed = 6 * exp(-3.5 * 0.05) ~ 5.037 km/h.

        Time along straight line = distance / 5.037 km/h.
        """
        slope = 0.0
        expected_speed = 6.0 * math.exp(-3.5 * 0.05)
        computed_speed = tobler_speed_kmh(slope)

        # Speed check
        assert math.isclose(computed_speed, expected_speed, rel_tol=1e-5)
        assert 5.03 < computed_speed < 5.04

        # Raster check: 50x50 flat plane with 30m cell size
        rows, cols = 40, 40
        cell_size = 30.0
        flat_dem = create_flat_dem(rows, cols, elevation=500.0)
        graph = CostGraph(
            dem=flat_dem,
            cell_size_x=cell_size,
            cell_size_y=cell_size,
            reversed_for_facilities=True,
        )

        # Place facility at (0, 0)
        dist_raster, _ = multi_source_dijkstra(graph, sources=[(0, 0)])

        # Cell (10, 0) is 10 cells south = 300 meters
        # Distance = 0.3 km, time = 0.3 / 5.03716 hrs * 60 min
        expected_time_min = (0.3 / expected_speed) * 60.0
        computed_time_min = dist_raster[10, 0]

        assert math.isclose(computed_time_min, expected_time_min, rel_tol=1e-3)

    def test_golden_constant_10_percent_uphill(self):
        """Golden Test 2: Constant 10% uphill matches closed-form.

        Slope S = +0.10.
        Speed v = 6 * exp(-3.5 * |0.10 + 0.05|) = 6 * exp(-3.5 * 0.15) ~ 3.5507 km/h.
        """
        slope = 0.10
        expected_speed = 6.0 * math.exp(-3.5 * 0.15)
        computed_speed = tobler_speed_kmh(slope)

        assert math.isclose(computed_speed, expected_speed, rel_tol=1e-5)
        assert 3.54 < computed_speed < 3.56

        # 3D distance for 30m horizontal and 3m rise (10% slope):
        h_dist = 30.0
        dz = 3.0
        dist_3d_km = math.hypot(h_dist, dz) / 1000.0
        expected_edge_min = (dist_3d_km / expected_speed) * 60.0

        computed_edge_min = edge_time_minutes(h_dist, dz)
        assert math.isclose(computed_edge_min, expected_edge_min, rel_tol=1e-5)

        # Test on raster: moving from row 10 to row 0 (facility at row 10, patient at row 0)
        # On reversed graph, travelling from facility outward models patient walking uphill to facility.
        dem_10pct = create_constant_slope_dem(20, 20, base_elevation=1000.0, slope=0.10)
        graph = CostGraph(dem=dem_10pct, cell_size_x=30.0, cell_size_y=30.0, reversed_for_facilities=True)
        dist_raster, _ = multi_source_dijkstra(graph, sources=[(10, 5)])

        # Cell (9, 5) is 1 cell away (30m horizontal, 3m drop from row 10 down to row 9)
        # In reversed graph: forward movement from (9,5) -> (10,5) is uphill (+3m)
        time_1_step = dist_raster[9, 5]
        assert math.isclose(time_1_step, expected_edge_min, rel_tol=1e-3)

    def test_golden_symmetric_ridge_asymmetry(self):
        """Golden Test 3: Asymmetry check.

        Because Tobler's function peaks at -0.05 slope, walking uphill from A to B
        takes a significantly different time than walking downhill from B to A.
        """
        dem_ridge = create_symmetric_ridge_dem(30, 31, base_elevation=1000.0, peak_elevation=1600.0)
        graph_fwd = CostGraph(dem=dem_ridge, cell_size_x=30.0, cell_size_y=30.0, reversed_for_facilities=False)

        # Uphill step from valley to ridge: col 0 to col 1
        time_uphill = graph_fwd.get_edge_time(15, 0, 15, 1)

        # Downhill step: col 1 to col 0
        time_downhill = graph_fwd.get_edge_time(15, 1, 15, 0)

        assert time_uphill > 0
        assert time_downhill > 0
        assert not math.isclose(time_uphill, time_downhill, rel_tol=0.1)
        # Uphill should take longer than downhill on a steep slope
        assert time_uphill > time_downhill

    def test_golden_river_barrier_with_and_without_bridge(self):
        """Golden Test 4: River barrier without bridge is impassable (infinite time);

        opening a bridge allows passage.
        """
        rows, cols = 15, 15
        flat_dem = create_flat_dem(rows, cols, elevation=500.0)

        # River divides col 7 from top to bottom
        river_mask = np.zeros((rows, cols), dtype=bool)
        river_mask[:, 7] = True

        # Graph WITHOUT bridge
        mod_no_bridge = TerrainModifiers(river_mask=river_mask, bridge_mask=None)
        graph_blocked = CostGraph(
            dem=flat_dem,
            cell_size_x=30.0,
            cell_size_y=30.0,
            modifiers=mod_no_bridge,
        )

        dist_no_bridge, _ = multi_source_dijkstra(graph_blocked, sources=[(7, 2)])
        # Target is at (7, 12), across the river
        assert math.isinf(dist_no_bridge[7, 12])

        # Graph WITH bridge at (7, 7)
        bridge_mask = np.zeros((rows, cols), dtype=bool)
        bridge_mask[7, 7] = True
        mod_with_bridge = TerrainModifiers(river_mask=river_mask, bridge_mask=bridge_mask)
        graph_bridged = CostGraph(
            dem=flat_dem,
            cell_size_x=30.0,
            cell_size_y=30.0,
            modifiers=mod_with_bridge,
        )

        dist_with_bridge, _ = multi_source_dijkstra(graph_bridged, sources=[(7, 2)])
        # Now target across the river is reachable
        assert not math.isinf(dist_with_bridge[7, 12])
        assert dist_with_bridge[7, 12] > 0


class TestPropertyBasedInvariants:
    """Property-based verification of mathematical and graph invariants."""

    def test_adding_facility_never_increases_travel_time(self):
        """Property: dist(h, F union {f_new}) <= dist(h, F) for all habitations h."""
        rows, cols = 30, 30
        dem = create_flat_dem(rows, cols)
        graph = CostGraph(dem, cell_size_x=30.0, cell_size_y=30.0)

        dist_1, _ = multi_source_dijkstra(graph, sources=[(5, 5)])
        dist_2, _ = multi_source_dijkstra(graph, sources=[(5, 5), (20, 20)])

        # Every cell must have time_2 <= time_1
        assert np.all(dist_2 <= dist_1 + 1e-9)

    def test_newly_covered_counts_exclude_already_served(self):
        """Requirement: candidate scoring counts ONLY newly covered population."""
        rows, cols = 30, 30
        dem = create_flat_dem(rows, cols)
        graph = CostGraph(dem, cell_size_x=30.0, cell_size_y=30.0)

        # Habitation 1: already served (e.g. current_time = 20 min <= 60 min threshold)
        h1 = HabitationPoint(
            id=1,
            name="Served Village",
            grid_coord=(5, 5),
            population=500,
            current_time_min=20.0,
            is_underserved=False,
        )
        # Habitation 2: underserved (current_time = 120 min > 60 min)
        h2 = HabitationPoint(
            id=2,
            name="Underserved Village",
            grid_coord=(6, 6),
            population=300,
            current_time_min=120.0,
            is_underserved=True,
        )

        # Place candidate at (5, 6) right next to both
        candidate = score_candidate(
            graph=graph,
            candidate_coord=(5, 6),
            candidate_id=99,
            habitations=[h1, h2],
            threshold_min=60.0,
        )

        # Only Habitation 2 should count towards gain_pop!
        assert h1.id not in candidate.newly_covered_habitations
        assert h2.id in candidate.newly_covered_habitations
        assert candidate.gain_pop == 300  # NOT 800!

    def test_greedy_equals_exact_on_small_instance(self):
        """Algorithm test: Greedy matches exact brute-force solver on small instances."""
        habs = [
            HabitationPoint(id=1, name="H1", grid_coord=(2, 2), population=100, is_underserved=True),
            HabitationPoint(id=2, name="H2", grid_coord=(2, 8), population=250, is_underserved=True),
            HabitationPoint(id=3, name="H3", grid_coord=(8, 2), population=400, is_underserved=True),
            HabitationPoint(id=4, name="H4", grid_coord=(8, 8), population=150, is_underserved=True),
        ]

        # Candidate 1 covers H1 & H2
        c1 = CandidateSite(id=101, grid_coord=(2, 5), gain_pop=350, newly_covered_habitations={1, 2})
        # Candidate 2 covers H3 & H4
        c2 = CandidateSite(id=102, grid_coord=(8, 5), gain_pop=550, newly_covered_habitations={3, 4})
        # Candidate 3 covers H2 & H4
        c3 = CandidateSite(id=103, grid_coord=(5, 8), gain_pop=400, newly_covered_habitations={2, 4})

        # Test k=1
        res_greedy_1 = select_facilities_greedy([c1, c2, c3], habs, k=1)
        res_exact_1 = select_facilities_exact([c1, c2, c3], habs, k=1)
        assert res_greedy_1.selected_candidate_ids == res_exact_1.selected_candidate_ids
        assert res_greedy_1.total_gain_pop == res_exact_1.total_gain_pop == 550
        assert res_greedy_1.selected_candidate_ids == [102]

        # Test k=2
        res_greedy_2 = select_facilities_greedy([c1, c2, c3], habs, k=2)
        res_exact_2 = select_facilities_exact([c1, c2, c3], habs, k=2)
        assert set(res_greedy_2.selected_candidate_ids) == set(res_exact_2.selected_candidate_ids)
        assert res_greedy_2.total_gain_pop == res_exact_2.total_gain_pop == 900
