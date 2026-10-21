"""Unit tests for facility siting optimization objectives."""

import pytest
from hillcare_geoengine.candidates import CandidateSite, HabitationPoint
from hillcare_geoengine.optimiser import select_facilities_greedy, select_facilities_exact


@pytest.fixture
def sample_habitations_and_candidates():
    habs = [
        HabitationPoint(id=1, name="Hab 1", grid_coord=(0, 0), population=500, sc_pct=40.0, is_underserved=True),
        HabitationPoint(id=2, name="Hab 2", grid_coord=(1, 1), population=300, sc_pct=10.0, is_underserved=True),
        HabitationPoint(id=3, name="Hab 3", grid_coord=(5, 5), population=200, sc_pct=80.0, is_underserved=True),
    ]

    # Candidate A covers Hab 1 (500 pop)
    cand_a = CandidateSite(id=1, grid_coord=(0, 1), gain_pop=500, newly_covered_habitations={1}, mean_time_delta=15.0)
    # Candidate B covers Hab 2 and Hab 3 (300 + 200 = 500 pop, high equity)
    cand_b = CandidateSite(id=2, grid_coord=(3, 3), gain_pop=500, newly_covered_habitations={2, 3}, mean_time_delta=20.0)

    return habs, [cand_a, cand_b]


def test_equity_weighted_objective_breaks_ties_towards_vulnerable(sample_habitations_and_candidates):
    """When raw population gain is tied (500 vs 500), equity weighting favors the site with higher SC/ST."""
    habs, candidates = sample_habitations_and_candidates

    # Raw coverage can pick either
    res_pop = select_facilities_greedy(candidates, habs, k=1, objective="max_new_coverage")
    assert res_pop.total_gain_pop == 500

    # Equity weighted:
    # Hab 1 equity = 500 * (1 + 0.40) = 700
    # Hab 2 + 3 equity = 300 * (1 + 0.10) + 200 * (1 + 0.80) = 330 + 360 = 690
    # Let's adjust cand_b to win equity:
    habs[2].sc_pct = 95.0
    # Hab 2 + 3 equity = 330 + 200 * 1.95 = 720 > 700
    res_equity = select_facilities_greedy(candidates, habs, k=1, objective="equity_weighted")
    assert res_equity.selected_candidate_ids == [2]


def test_greedy_stops_when_k_exceeds_uncovered_habitations(sample_habitations_and_candidates):
    """Greedy solver gracefully handles k larger than the number of candidates or needs."""
    habs, candidates = sample_habitations_and_candidates
    res = select_facilities_greedy(candidates, habs, k=5)
    # Only 2 candidates exist and together they cover all 3 habitations
    assert len(res.selected_candidate_ids) == 2
    assert res.total_gain_pop == 1000
