"""HillCare Access pipeline package.

Ingestion, database models, pipeline orchestration, seasonal SAR processing, and JEPA representations.
"""

from hillcare_pipeline.db import get_db_session, init_db, engine
from hillcare_pipeline.models import (
    Base,
    Region,
    DataSnapshot,
    DataIssue,
    Habitation,
    Facility,
    Run,
    TravelTime,
    Underserved,
    CandidateSiteRecord,
    Scenario,
    AppUser,
    AuditLog,
    EOFeature,
)
from hillcare_pipeline.ingest import ingest_district_fixture
from hillcare_pipeline.runner import run_pipeline_for_district

__all__ = [
    "get_db_session",
    "init_db",
    "engine",
    "Base",
    "Region",
    "DataSnapshot",
    "DataIssue",
    "Habitation",
    "Facility",
    "Run",
    "TravelTime",
    "Underserved",
    "CandidateSiteRecord",
    "Scenario",
    "AppUser",
    "AuditLog",
    "EOFeature",
    "ingest_district_fixture",
    "run_pipeline_for_district",
]
