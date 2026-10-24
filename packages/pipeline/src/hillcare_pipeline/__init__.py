"""HillCare Access pipeline package.

Ingestion, database models, pipeline orchestration, seasonal SAR processing, and JEPA representations.
"""

from hillcare_pipeline.db import engine, get_db_session, init_db
from hillcare_pipeline.ingest import ingest_district_fixture
from hillcare_pipeline.models import (
    AppUser,
    AuditLog,
    Base,
    CandidateSiteRecord,
    DataIssue,
    DataSnapshot,
    EOFeature,
    Facility,
    Habitation,
    Region,
    Run,
    Scenario,
    TravelTime,
    Underserved,
)
from hillcare_pipeline.runner import run_pipeline_for_district

__all__ = [
    "AppUser",
    "AuditLog",
    "Base",
    "CandidateSiteRecord",
    "DataIssue",
    "DataSnapshot",
    "EOFeature",
    "Facility",
    "Habitation",
    "Region",
    "Run",
    "Scenario",
    "TravelTime",
    "Underserved",
    "engine",
    "get_db_session",
    "ingest_district_fixture",
    "init_db",
    "run_pipeline_for_district",
]
