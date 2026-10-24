"""Unit and integration tests for HillCare Access REST API endpoints."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

root_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.extend([
    str(root_dir / "packages" / "geoengine" / "src"),
    str(root_dir / "packages" / "pipeline" / "src"),
    str(root_dir / "apps" / "api" / "src"),
])

import auth

from apps.api.src.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True


def test_list_regions():
    response = client.get("/api/v1/regions?level=district")
    assert response.status_code == 200
    districts = response.json()
    assert len(districts) >= 3
    names = [d["name"] for d in districts]
    assert "Pithoragarh" in names
    assert "Chamoli" in names
    assert "Rudraprayag" in names


def test_region_summary():
    # Pithoragarh has ID 1
    response = client.get("/api/v1/regions/1/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["region_name"] == "Pithoragarh"
    assert summary["total_population"] > 0
    assert summary["total_habitations"] > 0
    assert summary["mean_travel_time_min"] > 0
    assert 0 <= summary["underserved_pct_60min"] <= 100


def test_list_habitations():
    response = client.get("/api/v1/habitations?district_id=1&limit=10")
    assert response.status_code == 200
    res = response.json()
    assert res["total_count"] > 0
    assert len(res["items"]) <= 10

    item = res["items"][0]
    assert "travel_time_min" in item
    assert "base" in item["travel_time_min"]
    assert "underserved" in item
    assert "30" in item["underserved"]
    assert "60" in item["underserved"]


def test_list_facilities():
    response = client.get("/api/v1/facilities?district_id=1")
    assert response.status_code == 200
    facs = response.json()
    assert len(facs) > 0
    tiers = {f["tier"] for f in facs}
    assert "DH" in tiers or "CHC" in tiers or "PHC" in tiers


def test_get_current_run():
    response = client.get("/api/v1/runs/current?district=pithoragarh")
    assert response.status_code == 200
    run_meta = response.json()
    assert run_meta["status"] == "succeeded"
    assert "parameters" in run_meta


def test_list_candidates():
    response = client.get("/api/v1/candidates?district=pithoragarh")
    assert response.status_code == 200
    data = response.json()
    assert len(data["candidates"]) > 0
    cand = data["candidates"][0]
    assert cand["rank"] == 1
    assert cand["gain_pop"] >= 0


def test_create_scenario_as_planner(monkeypatch):
    monkeypatch.setenv("HILLCARE_ENABLE_DEV_AUTH", "true")
    payload = {
        "name": "Test Scenario - New PHC in Block A",
        "region_id": 1,
        "tier": "PHC",
        "threshold_min": 60.0,
        "mode": "hybrid",
        "objective": "max_new_coverage",
        "k": 1,
    }
    # Send planner header
    headers = {"X-User-Role": "planner", "X-User-Id": "test_planner"}
    response = client.post("/api/v1/scenarios", json=payload, headers=headers)
    assert response.status_code == 201
    scen = response.json()
    assert scen["id"].startswith("scen_")
    assert scen["status"] == "succeeded"
    assert scen["result"] is not None


def test_assistant_grounded_answer_and_live_stats():
    # Grounded query about Pithoragarh
    payload = {"query": "What is the underserved population in Pithoragarh?", "language": "en"}
    response = client.post("/api/v1/assistant", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert "Pithoragarh" in res["answer"]
    assert len(res["citations"]) > 0
    assert any("Pithoragarh" in c["source_title"] for c in res["citations"])


def test_assistant_medical_refusal_guardrail():
    # Query asking for medical prescription/treatment
    payload = {"query": "What medicine should I prescribe for acute chest pain and fever?", "language": "en"}
    response = client.post("/api/v1/assistant", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert "does not provide clinical medical advice" in res["answer"]
    assert any("Section 2.2 Non-Goals" in c["section"] for c in res["citations"])


def test_admin_endpoints_require_admin_role(monkeypatch):
    monkeypatch.setenv("HILLCARE_ENABLE_DEV_AUTH", "true")
    # Attempting to call admin ingest without admin role returns 403
    headers = {"X-User-Role": "anonymous"}
    response = client.post("/api/v1/admin/ingest", headers=headers)
    assert response.status_code == 403


def test_unverified_admin_credentials_are_not_trusted(monkeypatch):
    monkeypatch.setattr(auth, "ENVIRONMENT", "production")
    monkeypatch.delenv("HILLCARE_ENABLE_DEV_AUTH", raising=False)

    header_response = client.post(
        "/api/v1/admin/ingest",
        headers={"X-User-Role": "admin"},
    )
    bearer_response = client.post(
        "/api/v1/admin/ingest",
        headers={"Authorization": "Bearer admin_token"},
    )

    assert header_response.status_code == 403
    assert bearer_response.status_code == 403
