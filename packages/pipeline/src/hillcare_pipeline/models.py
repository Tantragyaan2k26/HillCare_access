"""SQLAlchemy declarative data models for HillCare Access.

Implements Section 7 database design, with support for PostgreSQL + PostGIS in production
and SQLite in development/testing.
"""

from __future__ import annotations
import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Region(Base):
    __tablename__ = "region"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(32), nullable=False)  # state, district, block
    lgd_code = Column(Integer, nullable=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("region.id"), nullable=True)
    geom_geojson = Column(Text, nullable=True)

    parent = relationship("Region", remote_side=[id], backref="children")
    habitations = relationship("Habitation", back_populates="region")
    facilities = relationship("Facility", back_populates="region")


class DataSnapshot(Base):
    __tablename__ = "data_snapshot"

    id = Column(String(64), primary_key=True)  # unique snapshot key or hash
    source = Column(String(128), nullable=False)  # Census, HMIS, GLO-30, Sentinel-1
    version = Column(String(64), nullable=False)
    sha256 = Column(String(64), nullable=False)
    licence = Column(String(128), nullable=True)
    fetched_at = Column(DateTime, default=datetime.datetime.utcnow)


class DataIssue(Base):
    __tablename__ = "data_issue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), ForeignKey("data_snapshot.id"), nullable=True)
    entity = Column(String(64), nullable=False)  # habitation, facility, road
    ref = Column(String(128), nullable=False)  # identifier / row
    issue_type = Column(String(64), nullable=False)  # bad_coords, outlier_pop, duplicate
    status = Column(String(32), default="open")  # open, resolved, ignored
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Habitation(Base):
    __tablename__ = "habitation"

    id = Column(Integer, primary_key=True)
    lgd_code = Column(Integer, nullable=True, index=True)
    name = Column(String(128), nullable=False)
    region_id = Column(Integer, ForeignKey("region.id"), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    elevation_m = Column(Float, nullable=False)
    population = Column(Integer, nullable=False)
    pop_year = Column(Integer, default=2011)
    sc_pct = Column(Float, default=0.0)
    st_pct = Column(Float, default=0.0)
    loc_quality = Column(String(64), default="census_centroid")
    snapshot_id = Column(String(64), ForeignKey("data_snapshot.id"), nullable=True)

    region = relationship("Region", back_populates="habitations")


class Facility(Base):
    __tablename__ = "facility"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    tier = Column(String(32), nullable=False)  # DH, CHC, PHC, HWC
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    elevation_m = Column(Float, nullable=False)
    region_id = Column(Integer, ForeignKey("region.id"), nullable=False, index=True)
    is_functional = Column(Boolean, default=True)
    doctor_count = Column(Integer, default=0)
    bed_count = Column(Integer, default=0)
    staffing_json = Column(Text, nullable=True)
    source_id = Column(String(128), nullable=True)
    snapshot_id = Column(String(64), ForeignKey("data_snapshot.id"), nullable=True)

    region = relationship("Region", back_populates="facilities")


class Run(Base):
    __tablename__ = "run"

    id = Column(String(64), primary_key=True)
    kind = Column(String(32), default="pipeline")  # pipeline or scenario
    params_json = Column(Text, nullable=False)
    code_sha = Column(String(64), nullable=True)
    image_digest = Column(String(128), nullable=True)
    status = Column(String(32), default="queued")  # queued, running, succeeded, failed
    created_by = Column(String(64), default="system")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class TravelTime(Base):
    __tablename__ = "travel_time"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("run.id"), nullable=False, index=True)
    habitation_id = Column(Integer, ForeignKey("habitation.id"), nullable=False, index=True)
    facility_id = Column(Integer, ForeignKey("facility.id"), nullable=True)
    walk_min = Column(Float, nullable=False)
    hybrid_min = Column(Float, nullable=False)
    walk_min_low = Column(Float, nullable=False)
    walk_min_high = Column(Float, nullable=False)


class Underserved(Base):
    __tablename__ = "underserved"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("run.id"), nullable=False, index=True)
    habitation_id = Column(Integer, ForeignKey("habitation.id"), nullable=False, index=True)
    threshold_min = Column(Float, nullable=False)
    mode = Column(String(32), default="walk")  # walk or hybrid
    is_underserved = Column(Boolean, default=True)


class CandidateSiteRecord(Base):
    __tablename__ = "candidate_site"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("run.id"), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    feasibility_json = Column(Text, nullable=True)
    gain_pop = Column(Integer, nullable=False)
    mean_time_delta = Column(Float, default=0.0)
    equity_score = Column(Float, default=0.0)
    rank = Column(Integer, default=0)


class Scenario(Base):
    __tablename__ = "scenario"

    id = Column(String(64), primary_key=True)
    owner_id = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    params_json = Column(Text, nullable=False)
    status = Column(String(32), default="queued")
    run_id = Column(String(64), ForeignKey("run.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AppUser(Base):
    __tablename__ = "app_user"

    id = Column(String(64), primary_key=True)
    cognito_sub = Column(String(64), unique=True, nullable=True)
    email = Column(String(128), unique=True, nullable=False)
    role = Column(String(32), default="planner")  # anonymous, planner, analyst, admin
    org_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    entity = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)
    ts = Column(DateTime, default=datetime.datetime.utcnow)


class EOFeature(Base):
    """Earth Observation / Satellite derived feature (v1.1)."""
    __tablename__ = "eo_feature"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), ForeignKey("data_snapshot.id"), nullable=True)
    feature_type = Column(String(64), nullable=False)  # trail, settlement, landslide, river_crossing
    confidence_score = Column(Float, default=0.85)
    status = Column(String(32), default="pending_review")  # pending_review, verified, rejected
    geom_geojson = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
