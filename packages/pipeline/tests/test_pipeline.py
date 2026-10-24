"""Integration and unit tests for HillCare Access ingestion and pipeline execution."""

import json
from pathlib import Path

import numpy as np
import pytest
import torch
from hillcare_pipeline.ingest import ingest_district_fixture
from hillcare_pipeline.jepa_encoder import DownstreamTrailHead, HimalayanJEPAEncoder
from hillcare_pipeline.models import (
    Base,
    CandidateSiteRecord,
    Facility,
    Habitation,
    Region,
    Run,
    TravelTime,
)
from hillcare_pipeline.runner import run_pipeline_for_district
from hillcare_pipeline.seasonal_sar import detect_sar_monsoon_disruptions
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SAMPLE_FIXTURE = Path("d:/GeoAI/data/sample/rudraprayag_sample.json")


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_ingest_sample_district(in_memory_db):
    """Test ingestion of sample fixture into database."""
    summary = ingest_district_fixture(in_memory_db, SAMPLE_FIXTURE)

    assert summary["district"] == "Rudraprayag"
    assert summary["habitations_ingested"] > 0
    assert summary["facilities_ingested"] > 0

    # Query database
    region = in_memory_db.query(Region).filter_by(name="Rudraprayag").first()
    assert region is not None
    assert len(region.children) > 0

    habs = in_memory_db.query(Habitation).all()
    assert len(habs) == summary["habitations_ingested"]

    facs = in_memory_db.query(Facility).all()
    assert len(facs) == summary["facilities_ingested"]


def test_end_to_end_pipeline_execution(in_memory_db):
    """Execute complete 10-stage pipeline on ingested district."""
    # 1. Ingest
    ingest_district_fixture(in_memory_db, SAMPLE_FIXTURE)
    district = in_memory_db.query(Region).filter_by(name="Rudraprayag").first()

    # 2. Run Pipeline
    result = run_pipeline_for_district(
        session=in_memory_db,
        district_id=district.id,
        tier="PHC",
        thresholds=[30.0, 60.0, 90.0],
        k_candidates=3,
    )

    assert result["run_id"].startswith("run_rudraprayag_")
    assert result["analysis_mode"] == "synthetic_demo"
    assert result["result_type"] == "synthetic_demo_estimate"
    assert result["total_habitations"] > 0
    assert result["total_population"] > 0
    assert result["top_candidates_selected"] > 0

    # Verify run record in database
    run_rec = in_memory_db.get(Run, result["run_id"])
    assert run_rec is not None
    assert run_rec.status == "succeeded"
    assert json.loads(run_rec.params_json)["analysis_mode"] == "synthetic_demo"
    assert json.loads(run_rec.params_json)["result_type"] == "synthetic_demo_estimate"

    # Verify travel times populated
    tt_records = in_memory_db.query(TravelTime).filter_by(run_id=result["run_id"]).all()
    assert len(tt_records) == result["total_habitations"]
    for tt in tt_records:
        assert tt.walk_min >= 0
        assert tt.hybrid_min >= 0

    # Verify candidate sites recorded
    cand_records = in_memory_db.query(CandidateSiteRecord).filter_by(run_id=result["run_id"]).all()
    assert len(cand_records) <= 3
    for cand in cand_records:
        assert cand.rank >= 1
        assert cand.gain_pop >= 0


def test_sar_monsoon_disruption_detection():
    """Verify SAR change detection on steep slope terrain."""
    rows, cols = 30, 30
    dry_sar = np.full((rows, cols), -12.0, dtype=np.float32)
    monsoon_sar = np.full((rows, cols), -12.0, dtype=np.float32)
    slopes = np.full((rows, cols), 10.0, dtype=np.float32)

    # Simulate landslide scar: -6 dB drop on 32 degree slope
    monsoon_sar[10:15, 10:15] = -18.5
    slopes[10:15, 10:15] = 32.0

    mask, metrics = detect_sar_monsoon_disruptions(
        dry_season_sar=dry_sar,
        monsoon_sar=monsoon_sar,
        slope_raster=slopes,
        change_threshold_db=-4.5,
        high_slope_threshold_deg=25.0,
    )

    assert metrics["landslide_trigger_count"] == 25
    assert np.all(mask[10:15, 10:15] == True)
    assert np.all(mask[0:5, 0:5] == False)


def test_jepa_encoder_and_trail_head_forward():
    """Verify PyTorch forward pass of I-JEPA representation encoder and downstream trail head."""
    encoder = HimalayanJEPAEncoder(img_size=32, patch_size=8, in_chans=4, embed_dim=64, depth=2, num_heads=2)
    trail_head = DownstreamTrailHead(embed_dim=64)

    # Simulated satellite tile batch: (B=2, C=4, H=32, W=32)
    x = torch.randn(2, 4, 32, 32)
    latents = encoder(x)
    assert latents.shape == (2, 16, 64)  # (32/8)^2 = 16 patches

    trail_preds = trail_head(latents)
    assert trail_preds.shape == (2, 16, 1)
    # Output is sigmoid probabilities
    assert torch.all(trail_preds >= 0.0) and torch.all(trail_preds <= 1.0)
