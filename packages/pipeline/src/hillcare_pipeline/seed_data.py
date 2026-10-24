"""Seed database with all sample pilot districts and execute published baseline runs."""

from pathlib import Path

from hillcare_pipeline.db import get_db_session, init_db
from hillcare_pipeline.ingest import ingest_district_fixture
from hillcare_pipeline.models import Region
from hillcare_pipeline.runner import run_pipeline_for_district

SAMPLE_DIR = Path("d:/GeoAI/data/sample")


def seed_all():
    print("Initializing HillCare database schema...")
    init_db()

    district_files = [
        SAMPLE_DIR / "pithoragarh_sample.json",
        SAMPLE_DIR / "chamoli_sample.json",
        SAMPLE_DIR / "rudraprayag_sample.json",
    ]

    with get_db_session() as session:
        for fpath in district_files:
            if fpath.exists():
                print(f"Ingesting fixture {fpath.name}...")
                ingest_summary = ingest_district_fixture(session, fpath)
                print(f"  -> Ingested: {ingest_summary}")

        districts = session.query(Region).filter_by(level="district").all()
        for d in districts:
            print(f"Executing baseline published run for {d.name}...")
            run_result = run_pipeline_for_district(
                session=session,
                district_id=d.id,
                run_id=f"run_baseline_{d.name.lower()}_current",
                tier="PHC",
                thresholds=[30.0, 60.0, 90.0],
                k_candidates=5,
            )
            print(f"  -> Run complete for {d.name}: {run_result['total_habitations']} habs, {run_result['underserved_habitations_60min']} underserved @ 60m, {run_result['top_candidates_selected']} candidate sites.")

    print("Data seeding and baseline runs complete!")


if __name__ == "__main__":
    seed_all()
