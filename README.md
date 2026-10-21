# HillCare Access

HillCare Access is a research prototype for geographic access analysis to health
facilities in hilly districts of Uttarakhand. The repository includes the API,
web application, geospatial packages, tests, infrastructure configuration, and
project documentation.

## Data

Local files under `data/` are intentionally not tracked. They include source
datasets, derived rasters, analysis outputs, and local databases; redistribution
rights and privacy cannot be established for every file. Review
[the provenance research](docs/data-provenance-research.md) before sourcing or
redistributing inputs. Real-data features require locally available project
data and are not populated by this source-only repository.

## Development security

Development role headers are disabled unless both `ENVIRONMENT=development`
and `HILLCARE_ENABLE_DEV_AUTH=true` are set. Enable this only for isolated local
development; it is not authentication for a deployed service. Bearer tokens
are not accepted as verified credentials. A production deployment requires a
configured identity-provider verifier before granting privileged roles.

Docker Compose requires `POSTGRES_PASSWORD` to be supplied through the local
environment; no database password is committed.
