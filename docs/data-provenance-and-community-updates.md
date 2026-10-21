# Data provenance, map interpretation, and update workflow

## Current data evidence

The local manifest is an index of the project team's claims; its publisher,
download-date, coverage, CRS, and license columns are not independently
authenticated evidence. Several raw artifacts were copied from a third-party
GitHub repository/release. SHA-256 values prove byte identity with the Phase 1
local inventory, not origin, authorship, or reuse rights.
For the source-by-source research review and inventory, see
[`data-provenance-research.md`](./data-provenance-research.md) and
[`provenance_research_source_inventory.csv`](./provenance_research_source_inventory.csv).

The provenance audit script creates its outputs in a new directory and never
edits source data:

```powershell
python scripts\audit_data_provenance.py
```

Review `data\provenance_audit_20261020_final\provenance_audit_report.md`,
`dataset_inventory.csv`, `data_issues.csv`, `facility_reconciliation.csv`,
and `habitation_boundary_reviews.csv`.

Facts established locally:

- Processed project GeoJSON layers declare OGC CRS84 and contain 3,368
  habitations, 484 facilities, 2,309 road geometries, and three boundaries.
- Processed habitation, facility, road and boundary layers contain no missing
  primary IDs under the checked field definitions; this does not authenticate
  an ID's issuer or source lineage. Raw PMGSY habitation/road ZIPs include
  WGS 84 `.prj` declarations.
- The processed facility CSV and GeoJSON both contain 484 rows; the manifest
  says 501. Phase 1 reproduced 503 with an earlier deduplication procedure and
  484 with a refined procedure. The path to 501 remains unknown.
- Nine habitations remain outside their assigned boundary: Chamoli 2,
  Pithoragarh 2, Rudraprayag 5. Do not silently move them or change assignments.
- Phase 2A DEM copies are EPSG:32644 at 30 m. Unsupported Pithoragarh source
  cells stay nodata; there are zero valid derived pixels east of the verified
  raw-source edge. No claim is made about terrain beyond that edge.
- The local raw NIC GeoJSON has no declared CRS. Its processed project
  geometries have a CRS84 declaration; that alone does not authenticate the
  original provider coordinates.
- WorldPop raster tags include a geographic-looking tiepoint, 30-arc-second
  pixel scale, and nodata value. The source file does not embed a CRS GeoKey;
  the filename and manifest are not sufficient to prove the exact product,
  year, or whether its cell values are counts versus density. It is not used
  to assign habitation population.

Official references checked on 20 October 2026:

- [Copernicus DEM product documentation](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)
  describes GLO-30 as a DSM/top-reflective surface and TanDEM-X acquisition
  during 2011–2015. The page states GLO-30/GLO-90 are freely available and
  prescribes source/adaptation attribution; the manifest's CC-BY-SA label is
  not established as the applicable license.
- [WorldPop product record](https://hub.worldpop.org/geodata/summary?id=24777)
  describes the cited WGS84 30-arc-second per-cell population product with DOI
  `10.5258/SOTON/WP00647`. This does not prove that the local 2020-named TIFF is
  that exact file/version.
- [OpenStreetMap copyright and attribution](https://www.openstreetmap.org/copyright)
  describes ODbL obligations. HillCare does not currently import, synchronize,
  or route over OSM data.
- NIC HealthGIS and PMGSY GeoSadak portal hostnames could not be retrieved from
  this environment. Their update mechanisms, access conditions, and licenses
  are therefore not claimed.

## User-facing map and metrics

The browser's **Real data map** calls the local read-only real-data API and
displays the processed source geometries. The map reports source-feature
counts, source attributes and IDs, and labels provider attribution as
unverified at record level. Selecting a habitation shows its nearest recorded
facility by spherical great-circle distance, in kilometres, using the
recorded coordinates and a mean Earth radius of 6,371.0088 km. This is not
road distance, terrain walking distance, or travel time. Road LineStrings
remain a display layer; no connected routing graph has been validated.
To improve initial loading, the real map requests roads only when that layer
is enabled; their browser-only SVG drawing is scale-simplified while the full
source geometries remain available in memory and in the separate API endpoint.
This display simplification does not change source coordinates or distances.

Existing sample-database views remain available with prominent demo labels.
Do not interpret their synthetic-terrain travel-time outputs as real-dataset
measurements.

## Community reports and review

Community contributions are stored in the separate
`data\community_reports.sqlite3` database. They are not merged into or used to
rewrite raw/processed source files or the existing HillCare application
database. Each submission starts with status `pending`. Reports contain no
submitter name, email, phone, or public user profile. Submitters can include
evidence source/URL, observation date, coordinates, and an optional related
report ID for corrections.

Reviewer listing, decision changes, and history require the
`HILLCARE_REVIEWER_TOKEN` environment variable and the `X-Reviewer-Token`
header. When the secret is not configured, reviewer operations return an
explicit unavailable response. The browser does not store the token. Review
events are append-only history records; accepted reports still do not
automatically change published source data.

## Manual source refresh (no live synchronization)

1. Request a dated, versioned export from the responsible official
   department/portal. Obtain a written license/redistribution statement and
   the source's CRS/schema documentation.
2. Save the received archive into a **new** staged snapshot directory. Record
   who supplied it, download timestamp, source URL/reference, product version,
   CRS, license text, original filename, file size, and SHA-256.
3. Validate schema, feature counts, ID coverage/duplicates, coordinate
   plausibility, district-boundary assignment, raster CRS/transform/nodata and
   coverage. Produce added/changed/removed record previews and a machine
   readable issue list. Keep unknown or changed records visible for review.
4. Have an authorized reviewer resolve provenance and spatial issues; never
   replace a previously published snapshot before approval. Preserve the
   prior snapshot and its hashes for reproducibility.
5. For OSM-derived extracts, record the extract timestamp and query/boundary,
   provide attribution and follow ODbL obligations. Do not scrape public tile
   servers or describe a static extract as live data.

No automated NIC/PMGSY/OSM synchronization has been implemented. The source
portal access, repeatable official export mechanism, per-file licensing, and
the manifest discrepancies remain blockers to a trustworthy automated import.

## Local launch

From a PowerShell window in `D:\GeoAI`:

```powershell
$env:HILLCARE_REVIEWER_TOKEN = "set-a-long-random-local-review-token"
$env:PYTHONPATH = "D:\GeoAI\apps\api\src;D:\GeoAI\packages\geoengine\src;D:\GeoAI\packages\pipeline\src"
python -m uvicorn main:app --app-dir apps\api\src --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
Set-Location D:\GeoAI\apps\web
.\node_modules\.bin\vite.cmd --host 127.0.0.1 --port 5173
```

Open <http://127.0.0.1:5173>. The API health endpoint is
<http://127.0.0.1:8000/health>.
