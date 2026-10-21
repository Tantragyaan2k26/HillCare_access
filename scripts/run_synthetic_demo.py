"""Run the existing synthetic pipeline against one sample fixture in memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "geoengine" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "pipeline" / "src"))

from hillcare_pipeline.ingest import ingest_district_fixture  # noqa: E402
from hillcare_pipeline.models import Base, Region  # noqa: E402
from hillcare_pipeline.runner import run_pipeline_for_district  # noqa: E402


FIXTURES = {
    "Chamoli": PROJECT_ROOT / "data" / "sample" / "chamoli_sample.json",
    "Pithoragarh": PROJECT_ROOT / "data" / "sample" / "pithoragarh_sample.json",
    "Rudraprayag": PROJECT_ROOT / "data" / "sample" / "rudraprayag_sample.json",
}


def run_demo(district_name: str, output_path: Path) -> dict[str, object]:
    if district_name not in FIXTURES:
        raise ValueError(f"Unsupported sample district: {district_name}")
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite synthetic output: {output_path}")
    fixture = FIXTURES[district_name]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        ingest_district_fixture(session, fixture)
        district = session.query(Region).filter_by(name=district_name, level="district").first()
        if district is None:
            raise ValueError(f"Fixture did not ingest district {district_name}.")
        result = run_pipeline_for_district(
            session=session,
            district_id=district.id,
            run_id=f"run_synthetic_demo_{district_name.lower()}",
            tier="PHC",
            thresholds=[30.0, 60.0, 90.0],
            k_candidates=3,
        )
    document = {
        **result,
        "schema_version": "1.0.0",
        "analysis_mode": "synthetic_demo",
        "result_type": "synthetic_demo_estimate",
        "synthetic": True,
        "fixture": str(fixture.relative_to(PROJECT_ROOT)),
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "database": "ephemeral in-memory SQLite; project database unchanged",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    engine.dispose()
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=tuple(FIXTURES), required=True)
    parser.add_argument("--output", type=Path, required=True, help="New JSON file; existing files are not overwritten.")
    args = parser.parse_args()
    result = run_demo(args.district, args.output)
    print(json.dumps({
        "analysis_mode": result["analysis_mode"],
        "result_type": result["result_type"],
        "district": result["district"],
        "output": str(args.output.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
