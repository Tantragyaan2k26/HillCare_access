"""Tests for real-data map endpoints and persistent community review records."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[3]
sys.path.extend([
    str(ROOT / "packages" / "geoengine" / "src"),
    str(ROOT / "packages" / "pipeline" / "src"),
    str(ROOT / "apps" / "api" / "src"),
])

from apps.api.src.main import app  # noqa: E402
from community_store import (  # noqa: E402
    CommunityBase,
    get_community_session,
)


client = TestClient(app)


def test_real_data_api_serves_source_counts_crs_and_geodesic_nearest():
    response = client.get("/api/v1/real-data/districts/Rudraprayag")

    assert response.status_code == 200
    data = response.json()
    assert data["analysis_mode"] == "real_data_map"
    assert data["counts"] == {
        "habitations": 652,
        "facilities": 66,
        "road_segments": 458,
        "district_boundaries": 1,
        "habitations_outside_assigned_boundary": 5,
    }
    assert data["crs"].startswith("OGC:CRS84")
    habitation = data["layers"]["habitations"][0]
    facility = habitation["nearest_facility"]
    assert facility["name"]
    assert facility["source_id"] is not None
    assert facility["distance_km"] > 0
    assert "great-circle" in facility["distance_method"]
    assert data["methodology"]["road_routing"] is False
    assert data["provenance"]["record_verification_status"].startswith("source attribution")
    assert len(data["layers"]["roads"]) == data["counts"]["road_segments"]

    without_roads = client.get("/api/v1/real-data/districts/Rudraprayag?include_roads=false")
    assert without_roads.status_code == 200
    assert without_roads.json()["layers"]["roads"] == []

    roads = client.get("/api/v1/real-data/districts/Rudraprayag/roads")
    assert roads.status_code == 200
    road_data = roads.json()
    assert road_data["crs"]["properties"]["name"].endswith("CRS84")
    assert road_data["count"] == data["counts"]["road_segments"]
    assert len(road_data["features"]) == data["counts"]["road_segments"]


def test_real_data_api_rejects_unknown_district():
    response = client.get("/api/v1/real-data/districts/Unknown")
    assert response.status_code == 404


def test_real_data_api_counts_and_boundary_review_flags_are_retained():
    expected = {
        "Chamoli": (1156, 218, 954, 2),
        "Pithoragarh": (1560, 200, 897, 2),
        "Rudraprayag": (652, 66, 458, 5),
    }
    for district, (habitations, facilities, roads, flagged) in expected.items():
        response = client.get(f"/api/v1/real-data/districts/{district}?include_roads=false")
        assert response.status_code == 200
        data = response.json()
        assert (
            data["counts"]["habitations"],
            data["counts"]["facilities"],
            data["counts"]["road_segments"],
            data["counts"]["habitations_outside_assigned_boundary"],
        ) == (habitations, facilities, roads, flagged)
        outliers = [
            feature for feature in data["layers"]["habitations"]
            if feature.get("review_flags")
        ]
        assert len(outliers) == flagged
        assert all(feature["properties"]["district"] == district for feature in outliers)
        roads = client.get(f"/api/v1/real-data/districts/{district}/roads")
        assert roads.status_code == 200
        assert roads.json()["count"] == len(roads.json()["features"])


def test_community_submission_persists_pending_and_review_history(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'reports.sqlite3').as_posix()}")
    CommunityBase.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def test_session():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_community_session] = test_session
    monkeypatch.setenv("HILLCARE_REVIEWER_TOKEN", "unit-test-reviewer-token")
    try:
        payload = {
            "category": "missing_facility",
            "district": "Chamoli",
            "latitude": 30.4,
            "longitude": 79.2,
            "subject": "Clinic shown as closed",
            "description": "The recorded facility has been closed since the date stated below.",
            "evidence_source": "District notice reference 42",
            "observed_on": "2026-09-01",
        }
        created = client.post("/api/v1/community-reports", json=payload)
        assert created.status_code == 201
        receipt = created.json()
        assert receipt["status"] == "pending"
        assert receipt["observed_on"] == "2026-09-01"
        report_id = receipt["id"]

        public_status = client.get(f"/api/v1/community-reports/{report_id}")
        assert public_status.status_code == 200
        assert public_status.json()["status"] == "pending"
        assert "description" not in public_status.json()
        assert "email" not in public_status.json()
        assert "personal" not in public_status.json()

        unauthorized = client.patch(
            f"/api/v1/community-reports/{report_id}",
            json={"status": "officially-confirmed", "note": "checked"},
        )
        assert unauthorized.status_code == 403

        queue = client.get(
            "/api/v1/community-reports",
            headers={"X-Reviewer-Token": "unit-test-reviewer-token"},
        )
        assert queue.status_code == 200
        assert queue.json()[0]["description"] == payload["description"]

        reviewed = client.patch(
            f"/api/v1/community-reports/{report_id}",
            headers={"X-Reviewer-Token": "unit-test-reviewer-token"},
            json={"status": "community-confirmed", "note": "Cross-checked with cited district notice."},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "community-confirmed"

        history = client.get(
            f"/api/v1/community-reports/{report_id}/history",
            headers={"X-Reviewer-Token": "unit-test-reviewer-token"},
        )
        assert history.status_code == 200
        assert [item["new_status"] for item in history.json()] == ["pending", "community-confirmed"]
        assert history.json()[1]["previous_status"] == "pending"
    finally:
        app.dependency_overrides.pop(get_community_session, None)
        engine.dispose()


def test_community_report_requires_evidence_and_valid_geographic_coordinates():
    response = client.post("/api/v1/community-reports", json={
        "category": "road_update",
        "district": "Pithoragarh",
        "latitude": 99,
        "longitude": 79,
        "subject": "Road issue",
        "description": "A road has changed.",
        "evidence_source": "Field observation",
    })
    assert response.status_code == 422
