"""API configuration settings and environment variables."""

import os
from pathlib import Path

DEFAULT_DB = Path("d:/GeoAI/data/hillcare.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB.as_posix()}")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "*",
]
