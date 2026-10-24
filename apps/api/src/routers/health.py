"""Health and readiness endpoints."""

from fastapi import APIRouter
from hillcare_pipeline.db import get_db_session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get("/api/v1/health")
def health_check():
    """Liveness and readiness health check."""
    db_ok = True
    try:
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database_connected": db_ok,
        "service": "HillCare Access API",
        "version": "1.1.0",
    }
