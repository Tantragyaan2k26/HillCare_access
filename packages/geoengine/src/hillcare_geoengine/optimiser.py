"""Facility siting optimization: maximal coverage, equity-weighted, and mean-travel-time objectives.

Implements greedy submodular optimization (with 1 - 1/e approximation guarantee)
and exact combinatorial search for small candidate sets.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from hillcare_geoengine.candidates import CandidateSite, HabitationPoint


@dataclass
class OptimizationResult:
    """Result of facility siting optimization."""
    objective: str
    k: int
    selected_candidate_ids: list[int]
    total_gain_pop: int
    newly_covered_habitations: set[int]
    marginal_gains: list[int] = field(default_factory=list)
    cumulative_pop_coverage_pct: float = 0.0


def select_facilities_greedy(
    candidates: list[CandidateSite],
    habitations: list[HabitationPoint],
    k: int = 1,
    objective: str = "max_new_coverage",
) -> OptimizationResult:
    """Select k facilities using the greedy algorithm.

    For submodular maximal coverage, the greedy heuristic guarantees at least
    a (1 - 1/e) ~ 63.2% approximation to the optimal solution.

    Args:
        candidates: Pre-scored candidate sites.
        habitations: All habitations in scope.
        k: Number of facilities to place.
        objective: 'max_new_coverage', 'equity_weighted', 'min_mean_time'.
    """
    feasible_candidates = [c for c in candidates if c.is_feasible]
    if not feasible_candidates or k <= 0:
        return OptimizationResult(
            objective=objective,
            k=k,
            selected_candidate_ids=[],
            total_gain_pop=0,
            newly_covered_habitations=set(),
        )

    hab_by_id: dict[int, HabitationPoint] = {h.id: h for h in habitations}
    total_underserved_pop = sum(h.population for h in habitations if h.is_underserved)

    selected_ids: list[int] = []
    already_covered: set[int] = set()
    marginal_gains: list[int] = []
    total_gain = 0

    available_candidates = list(feasible_candidates)

    for _ in range(min(k, len(available_candidates))):
        best_candidate: CandidateSite | None = None
        best_marginal_score: float = -1.0
        best_new_habs: set[int] = set()
        best_pop_gain: int = 0

        for cand in available_candidates:
            # Habitations covered by this candidate that are not yet covered
            uncovered_here = cand.newly_covered_habitations - already_covered
            pop_gain = sum(hab_by_id[hid].population for hid in uncovered_here if hid in hab_by_id)

            if objective == "max_new_coverage":
                score = float(pop_gain)
            elif objective == "equity_weighted":
                score = sum(
                    hab_by_id[hid].population * (1.0 + ((hab_by_id[hid].sc_pct + hab_by_id[hid].st_pct) / 100.0))
                    for hid in uncovered_here if hid in hab_by_id
                )
            elif objective == "min_mean_time":
                score = cand.mean_time_delta
            else:
                score = float(pop_gain)

            if score > best_marginal_score:
                best_marginal_score = score
                best_candidate = cand
                best_new_habs = uncovered_here
                best_pop_gain = pop_gain

        if best_candidate is None or (best_pop_gain == 0 and objective == "max_new_coverage"):
            # No further improvement possible
            break

        selected_ids.append(best_candidate.id)
        already_covered.update(best_new_habs)
        marginal_gains.append(best_pop_gain)
        total_gain += best_pop_gain
        available_candidates.remove(best_candidate)

    cov_pct = (total_gain / total_underserved_pop * 100.0) if total_underserved_pop > 0 else 100.0

    return OptimizationResult(
        objective=objective,
        k=k,
        selected_candidate_ids=selected_ids,
        total_gain_pop=total_gain,
        newly_covered_habitations=already_covered,
        marginal_gains=marginal_gains,
        cumulative_pop_coverage_pct=cov_pct,
    )


def select_facilities_exact(
    candidates: list[CandidateSite],
    habitations: list[HabitationPoint],
    k: int = 1,
) -> OptimizationResult:
    """Exact combinatorial solver for small candidate sets (brute force benchmark).

    Evaluates all combinations C(N, k) to find the global optimum for maximal coverage.
    """
    feasible = [c for c in candidates if c.is_feasible]
    if not feasible or k <= 0:
        return OptimizationResult(
            objective="max_new_coverage_exact",
            k=k,
            selected_candidate_ids=[],
            total_gain_pop=0,
            newly_covered_habitations=set(),
        )

    hab_by_id = {h.id: h for h in habitations}
    total_underserved_pop = sum(h.population for h in habitations if h.is_underserved)

    best_combo: tuple[CandidateSite, ...] | None = None
    best_gain = -1
    best_covered_set: set[int] = set()

    for combo in itertools.combinations(feasible, min(k, len(feasible))):
        union_covered: set[int] = set()
        for c in combo:
            union_covered.update(c.newly_covered_habitations)
        gain = sum(hab_by_id[hid].population for hid in union_covered if hid in hab_by_id)
        if gain > best_gain:
            best_gain = gain
            best_combo = combo
            best_covered_set = union_covered

    selected_ids = [c.id for c in best_combo] if best_combo else []
    cov_pct = (best_gain / total_underserved_pop * 100.0) if total_underserved_pop > 0 else 100.0

    return OptimizationResult(
        objective="max_new_coverage_exact",
        k=k,
        selected_candidate_ids=selected_ids,
        total_gain_pop=max(best_gain, 0),
        newly_covered_habitations=best_covered_set,
        cumulative_pop_coverage_pct=cov_pct,
    )
