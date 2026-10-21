"""Pipeline orchestration runner for HillCare Access.

Executes the complete 10-stage batch process:
ingest -> grid -> cost surface -> travel times -> extraction -> classification ->
candidates -> scoring -> selection -> publish.
"""

from __future__ import annotations
import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
from sqlalchemy.orm import Session

from hillcare_geoengine.cost_surface import CostGraph, TerrainModifiers
from hillcare_geoengine.dijkstra import multi_source_dijkstra, bounded_dijkstra
from hillcare_geoengine.candidates import (
    CandidateSite,
    HabitationPoint,
    score_candidate,
)
from hillcare_geoengine.optimiser import select_facilities_greedy
from hillcare_geoengine.raster import create_synthetic_himalayan_valley

from hillcare_pipeline.models import (
    CandidateSiteRecord,
    Facility,
    Habitation,
    Region,
    Run,
    TravelTime,
    Underserved,
)


def run_pipeline_for_district(
    session: Session,
    district_id: int,
    run_id: Optional[str] = None,
    tier: str = "PHC",
    thresholds: List[float] = [30.0, 60.0, 90.0],
    k_candidates: int = 5,
    is_monsoon: bool = False,
    disruption_mask: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Execute the end-to-end access analysis and siting pipeline for a district.

    Args:
        session: Active database session.
        district_id: ID of the district to process.
        run_id: Unique identifier for this run.
        tier: Facility tier being analysed ('PHC', 'CHC', 'DH', 'HWC').
        thresholds: List of minutes for underserved classification (e.g. [30, 60, 90]).
        k_candidates: Number of top candidate sites to recommend.
        is_monsoon: If True, evaluates seasonal monsoon conditions.
        disruption_mask: Optional SAR-derived disruption mask.

    Returns:
        Summary metrics and statistics of the published run.
    """
    district = session.get(Region, district_id)
    if not district:
        raise ValueError(f"District ID {district_id} not found in database.")

    if run_id is None:
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_id = f"run_{district.name.lower()}_{ts}"

    params = {
        "analysis_mode": "synthetic_demo",
        "result_type": "synthetic_demo_estimate",
        "district_id": district_id,
        "district_name": district.name,
        "tier": tier,
        "thresholds_min": thresholds,
        "k_candidates": k_candidates,
        "is_monsoon": is_monsoon,
    }

    # 1. Initialize Run record
    run_record = Run(
        id=run_id,
        kind="pipeline",
        params_json=json.dumps(params),
        code_sha="v1.1-oct2026",
        status="running",
        created_by="system_pipeline",
    )
    session.add(run_record)
    session.flush()

    # 2. Query habitations in this district (including all its blocks)
    # Blocks have parent_id = district_id
    sub_region_ids = [r.id for r in district.children] + [district_id]
    db_habs = session.query(Habitation).filter(Habitation.region_id.in_(sub_region_ids)).all()

    # Query facilities of matching tier
    tier_hierarchy = {
        "HWC": ["HWC", "PHC", "CHC", "DH"],
        "PHC": ["PHC", "CHC", "DH"],
        "CHC": ["CHC", "DH"],
        "DH": ["DH"],
    }
    eligible_tiers = tier_hierarchy.get(tier, [tier])
    db_facs = (
        session.query(Facility)
        .filter(Facility.region_id.in_(sub_region_ids))
        .filter(Facility.tier.in_(eligible_tiers))
        .filter(Facility.is_functional == True)
        .all()
    )

    if not db_habs:
        run_record.status = "failed"
        session.flush()
        return {"error": "No habitations found for district."}

    # 3. Create grid bounding box and coordinate mapping
    lats = [h.lat for h in db_habs] + [f.lat for f in db_facs]
    lons = [h.lon for h in db_habs] + [f.lon for f in db_facs]
    min_lat, max_lat = min(lats) - 0.05, max(lats) + 0.05
    min_lon, max_lon = min(lons) - 0.05, max(lons) + 0.05

    # 60x60 grid resolution over the district window
    grid_rows, grid_cols = 60, 60
    lat_step = (max_lat - min_lat) / (grid_rows - 1)
    lon_step = (max_lon - min_lon) / (grid_cols - 1)

    def geo_to_grid(lat: float, lon: float) -> Tuple[int, int]:
        r = int(round((lat - min_lat) / lat_step))
        c = int(round((lon - min_lon) / lon_step))
        return max(0, min(grid_rows - 1, r)), max(0, min(grid_cols - 1, c))

    def grid_to_geo(r: int, c: int) -> Tuple[float, float]:
        lat = min_lat + r * lat_step
        lon = min_lon + c * lon_step
        return round(lat, 5), round(lon, 5)

    # 4. Generate DEM and Cost Surface with realistic geographic cell scaling
    mid_lat = (min_lat + max_lat) / 2.0
    dy_meters = (max_lat - min_lat) * 111320.0
    dx_meters = (max_lon - min_lon) * 111320.0 * math.cos(math.radians(mid_lat))
    cell_size_y = max(30.0, dy_meters / (grid_rows - 1))
    cell_size_x = max(30.0, dx_meters / (grid_cols - 1))

    base_elev = 800.0 if district.name == "Rudraprayag" else 1500.0
    dem = create_synthetic_himalayan_valley(
        rows=grid_rows,
        cols=grid_cols,
        cell_size=min(cell_size_x, cell_size_y),
        base_elevation=base_elev,
        max_elevation=base_elev + 1600.0,
    )

    # Modifiers: Road & River simulation across grid
    road_mask = np.zeros((grid_rows, grid_cols), dtype=bool)
    road_mask[grid_rows // 2, :] = True  # main highway across the district
    river_mask = np.zeros((grid_rows, grid_cols), dtype=bool)
    river_mask[:, grid_cols // 2] = True  # gorge cutting north-south
    bridge_mask = np.zeros((grid_rows, grid_cols), dtype=bool)
    bridge_mask[grid_rows // 2, grid_cols // 2] = True  # bridge where road crosses river

    modifiers = TerrainModifiers(
        road_mask=road_mask,
        road_vehicle_speed_kmh=25.0,
        river_mask=river_mask,
        bridge_mask=bridge_mask,
        disruption_mask=disruption_mask,
    )

    # 5. Build Graphs for base, low, and high speeds
    graph_base = CostGraph(dem, cell_size_x, cell_size_y, modifiers=modifiers, calibration=1.0)
    graph_low = CostGraph(dem, cell_size_x, cell_size_y, modifiers=modifiers, calibration=0.8)
    graph_high = CostGraph(dem, cell_size_x, cell_size_y, modifiers=modifiers, calibration=1.2)

    # Map facilities to grid sources
    fac_sources: List[Tuple[int, int]] = []
    fac_ids: List[int] = []
    for f in db_facs:
        r, c = geo_to_grid(f.lat, f.lon)
        fac_sources.append((r, c))
        fac_ids.append(f.id)

    # 6. Multi-source Dijkstra (Walk-only and Hybrid modes)
    dist_walk_base, nearest_fac_raster = multi_source_dijkstra(
        graph_base, sources=fac_sources, source_ids=fac_ids, is_hybrid=False
    )
    dist_walk_low, _ = multi_source_dijkstra(
        graph_low, sources=fac_sources, source_ids=fac_ids, is_hybrid=False
    )
    dist_walk_high, _ = multi_source_dijkstra(
        graph_high, sources=fac_sources, source_ids=fac_ids, is_hybrid=False
    )
    dist_hybrid_base, _ = multi_source_dijkstra(
        graph_base, sources=fac_sources, source_ids=fac_ids, is_hybrid=True, initial_delay_minutes=20.0
    )

    # 7. Extract travel time per habitation & Classify Underserved
    hab_points: List[HabitationPoint] = []
    travel_time_records: List[TravelTime] = []
    underserved_records: List[Underserved] = []

    served_count_60 = 0
    underserved_count_60 = 0
    total_pop = 0
    underserved_pop_60 = 0

    for h in db_habs:
        hr, hc = geo_to_grid(h.lat, h.lon)
        t_walk = float(dist_walk_base[hr, hc])
        t_low = float(dist_walk_low[hr, hc])
        t_high = float(dist_walk_high[hr, hc])
        t_hyb = float(dist_hybrid_base[hr, hc])
        near_fid = int(nearest_fac_raster[hr, hc])

        # Clamp if unreachable
        if math.isinf(t_walk):
            t_walk = 999.0
            t_low = 999.0
            t_high = 999.0
        if math.isinf(t_hyb):
            t_hyb = t_walk

        tt_rec = TravelTime(
            run_id=run_id,
            habitation_id=h.id,
            facility_id=near_fid if near_fid >= 0 else None,
            walk_min=round(t_walk, 1),
            hybrid_min=round(t_hyb, 1),
            walk_min_low=round(t_low, 1),
            walk_min_high=round(t_high, 1),
        )
        travel_time_records.append(tt_rec)

        is_under_60 = t_walk > 60.0
        total_pop += h.population
        if is_under_60:
            underserved_count_60 += 1
            underserved_pop_60 += h.population
        else:
            served_count_60 += 1

        # Record underserved flags for all thresholds
        for thr in thresholds:
            underserved_records.append(
                Underserved(
                    run_id=run_id,
                    habitation_id=h.id,
                    threshold_min=thr,
                    mode="walk",
                    is_underserved=(t_walk > thr),
                )
            )

        hab_points.append(
            HabitationPoint(
                id=h.id,
                name=h.name,
                grid_coord=(hr, hc),
                population=h.population,
                sc_pct=h.sc_pct,
                st_pct=h.st_pct,
                current_time_min=t_walk,
                is_underserved=is_under_60,
            )
        )

    session.bulk_save_objects(travel_time_records)
    session.bulk_save_objects(underserved_records)

    # 8. Candidate Facility Generation & Scoring (60-minute threshold)
    candidate_sites: List[CandidateSite] = []
    cand_id_seq = 1

    # Candidates prioritized from underserved habitations, or most remote habitations
    target_habs = [h for h in hab_points if h.is_underserved]
    if not target_habs:
        target_habs = sorted(hab_points, key=lambda h: h.current_time_min, reverse=True)

    for h in target_habs[:25]:
        cand = score_candidate(
            graph=graph_base,
            candidate_coord=h.grid_coord,
            candidate_id=cand_id_seq,
            habitations=hab_points,
            threshold_min=60.0,
            is_existing_settlement=True,
        )
        candidate_sites.append(cand)
        cand_id_seq += 1

    # 9. Optimal Site Selection (Greedy submodular maximization)
    opt_result = select_facilities_greedy(
        candidates=candidate_sites,
        habitations=hab_points,
        k=k_candidates,
        objective="max_new_coverage",
    )
    # If raw coverage yielded no candidates (e.g. all served <= 60 min), optimize for time reduction
    if not opt_result.selected_candidate_ids and candidate_sites:
        opt_result = select_facilities_greedy(
            candidates=candidate_sites,
            habitations=hab_points,
            k=k_candidates,
            objective="min_mean_time",
        )
    # Fallback to top feasible candidate if scores were zero
    if not opt_result.selected_candidate_ids and candidate_sites:
        opt_result.selected_candidate_ids = [candidate_sites[0].id]

    # 10. Persist Top Candidates
    cand_records: List[CandidateSiteRecord] = []
    for rank, cid in enumerate(opt_result.selected_candidate_ids, start=1):
        cand = next(c for c in candidate_sites if c.id == cid)
        c_lat, c_lon = grid_to_geo(cand.grid_coord[0], cand.grid_coord[1])
        cand_records.append(
            CandidateSiteRecord(
                run_id=run_id,
                lat=c_lat,
                lon=c_lon,
                feasibility_json=json.dumps({"notes": cand.feasibility_notes, "grid": cand.grid_coord}),
                gain_pop=cand.gain_pop,
                mean_time_delta=round(cand.mean_time_delta, 2),
                equity_score=round(cand.equity_score, 1),
                rank=rank,
            )
        )

    session.bulk_save_objects(cand_records)

    # Finalize Run Record
    run_record.status = "succeeded"
    run_record.finished_at = datetime.datetime.utcnow()
    session.flush()

    pct_underserved = round((underserved_pop_60 / total_pop * 100.0), 1) if total_pop > 0 else 0.0

    return {
        "analysis_mode": "synthetic_demo",
        "result_type": "synthetic_demo_estimate",
        "run_id": run_id,
        "district": district.name,
        "tier": tier,
        "total_habitations": len(db_habs),
        "total_population": total_pop,
        "underserved_habitations_60min": underserved_count_60,
        "underserved_population_60min": underserved_pop_60,
        "pct_underserved_60min": pct_underserved,
        "top_candidates_selected": len(cand_records),
        "total_newly_covered_population": opt_result.total_gain_pop,
    }
