# Project: HillCare Access
Purpose: slope-adjusted (Tobler) walking-time access analysis to health facilities in hilly Indian districts, with an optimiser suggesting new facility sites.

## Principles
- Heavy compute is offline (batch). The API serves precomputed results.
- All runs are reproducible: store params, code SHA, data snapshot IDs.
- Travel time is HABITATION -> FACILITY. Use the reversed graph for multi-source search.
- Count only NEWLY covered population when scoring candidate sites.
- Never claim to measure unmet need; say "geographic access".

## Stack
Python 3.12 (FastAPI, SQLAlchemy, Alembic, rasterio/tifffile, numpy, numba/scipy, geopandas/shapely, pyproj, ortools/scipy.optimize), PostgreSQL 16 + PostGIS, Redis, React + TypeScript + Vite + MapLibre, Terraform, GitHub Actions, AWS (ECS Fargate, Batch, S3, RDS, CloudFront, Cognito, WAF).

## Conventions
- Conventional Commits; small PRs; tests with every change.
- Type hints everywhere; ruff + mypy + eslint must pass.
- No secrets in code. Config via environment variables.
- Parameterised SQL only. Validate all input with Pydantic.
- Geometries: store EPSG:4326, compute in UTM (EPSG:32644 / 32643).

## Build order
Follow Section 17 phases in order. Start with packages/geoengine and its golden tests BEFORE any API or UI work. Ask before changing the schema in Section 7.

## Definition of done (every task)
Tests pass, lint passes, docs updated, no new high-severity vulnerabilities.
