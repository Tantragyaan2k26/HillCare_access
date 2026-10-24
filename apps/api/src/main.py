"""FastAPI application entry point for HillCare Access."""

import sys
from pathlib import Path

# Ensure packages are discoverable
root_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.extend([
    str(root_dir / "packages" / "geoengine" / "src"),
    str(root_dir / "packages" / "pipeline" / "src"),
    str(Path(__file__).resolve().parent),
])

from config import CORS_ORIGINS
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers import (
    admin,
    assistant,
    candidates,
    community_reports,
    facilities,
    habitations,
    health,
    real_data,
    regions,
    runs,
    scenarios,
)
from schemas import ProblemDetails

app = FastAPI(
    title="HillCare Access REST API",
    version="1.1.0",
    description=(
        "Slope-adjusted health-facility access analysis for hilly districts of India. "
        "Calculates realistic walking times using Tobler's Hiking Function on terrain graphs, "
        "identifies underserved habitations, recommends optimal facility siting, and provides "
        "an AI-powered health planner assistant (v1.1)."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# RFC 7807 Problem Details Error Handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ProblemDetails(
            type="https://hillcare.org/errors/http-error",
            title=exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            status=exc.status_code,
            detail=str(exc.detail),
            trace_id=request.headers.get("x-request-id"),
        ).model_dump(),
    )


# Register Routers
app.include_router(health.router)
app.include_router(regions.router)
app.include_router(real_data.router)
app.include_router(community_reports.router)
app.include_router(habitations.router)
app.include_router(facilities.router)
app.include_router(runs.router)
app.include_router(candidates.router)
app.include_router(scenarios.router)
app.include_router(assistant.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {
        "name": "HillCare Access API",
        "version": "1.1.0",
        "docs": "/api/docs",
        "health": "/health",
    }
