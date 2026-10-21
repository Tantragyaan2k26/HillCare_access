"""Pydantic schemas and API contracts for HillCare Access."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TravelTimeRange(BaseModel):
    base: float
    low: float
    high: float


class NearestFacility(BaseModel):
    id: int
    name: str
    tier: str


class HabitationItem(BaseModel):
    id: int
    name: str
    block: Optional[str] = None
    lat: float
    lon: float
    elevation_m: float
    population: int
    sc_pct: float
    st_pct: float
    travel_time_min: TravelTimeRange
    hybrid_time_min: float
    nearest_facility: Optional[NearestFacility] = None
    underserved: Dict[str, bool]  # e.g. {"30": True, "60": True, "90": False}
    quality_flags: List[str] = Field(default_factory=list)


class HabitationListResponse(BaseModel):
    run_id: str
    total_count: int
    items: List[HabitationItem]
    next_cursor: Optional[str] = None


class FacilityItem(BaseModel):
    id: int
    name: str
    tier: str
    lat: float
    lon: float
    elevation_m: float
    region_id: int
    is_functional: bool
    doctor_count: int
    bed_count: int


class RegionSummary(BaseModel):
    region_id: int
    region_name: str
    level: str
    total_population: int
    total_habitations: int
    mean_travel_time_min: float
    median_travel_time_min: float
    underserved_pct_30min: float
    underserved_pct_60min: float
    underserved_pct_90min: float
    functional_facilities_count: int


class CandidateItem(BaseModel):
    id: int
    rank: int
    lat: float
    lon: float
    gain_pop: int
    mean_time_delta: float
    equity_score: float
    feasibility: Dict[str, Any] = Field(default_factory=dict)


class CandidateListResponse(BaseModel):
    run_id: str
    objective: str
    candidates: List[CandidateItem]


class ScenarioCreateRequest(BaseModel):
    name: str
    region_id: int
    tier: str = "PHC"
    threshold_min: float = 60.0
    mode: str = "hybrid"  # walk or hybrid
    objective: str = "max_new_coverage"
    k: int = 1
    calibration: float = 1.0
    hypothetical_facility_lat: Optional[float] = None
    hypothetical_facility_lon: Optional[float] = None


class ScenarioResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    status: str  # queued, running, succeeded, failed
    params: Dict[str, Any]
    run_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class AssistantCitation(BaseModel):
    source_title: str
    section: Optional[str] = None
    quote: str
    uri: Optional[str] = None


class AssistantQueryRequest(BaseModel):
    query: str
    language: str = "en"  # "en" or "hi"
    district_id: Optional[int] = None


class AssistantResponse(BaseModel):
    query: str
    language: str
    answer: str
    citations: List[AssistantCitation]
    tool_calls_executed: List[str] = Field(default_factory=list)


class ProblemDetails(BaseModel):
    type: str = "validation_error"
    title: str
    status: int
    detail: str
    trace_id: Optional[str] = None
