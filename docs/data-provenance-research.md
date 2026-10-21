# HillCare Access data provenance research

**Research snapshot: 20 October 2026**

This note distinguishes evidence about the files in this project from claims
about where those files originated. It is intended for research review, not
for display in the application. A publisher name in a manifest, a plausible
filename, or an identifier inside a feature does not prove that a publisher
created or authenticated that particular record.

## Plain-language summary

The project’s real-data files came into the repository through a mixture of
third-party GitHub mirrors and a Copernicus-named public object-store location
listed in the manifest. We have local file hashes, source IDs, processing
descriptions, spatial metadata and locally reproduced record counts. We do
not have signed publisher checksums, original download logs or a versioned
official export for the NIC, PMGSY or district-boundary vectors. Their
publisher attribution and licensing therefore remain claims, not verified
record-level provenance.

The local map is useful for inspecting the coordinates and attributes as
currently stored. It is not evidence that each facility is open, staffed, or
still at that location, nor that every road is current or connected. The
facility manifest count (501) does not match the retained local output (484).
Nine habitation points fall outside their assigned local district boundary
and remain explicitly flagged for review.

## What the local evidence establishes

- The Phase 1 audit compared **31 local source/input files** with its
  [SHA-256 inventory](../data/audit_phase1_20261020/source_hash_inventory.csv):
  **31 matched; zero missing or mismatched** at this research check. The
  hashes establish byte identity with that local inventory only. They do not
  identify an original publisher.
- The processed geographic feature counts are 3,368 habitations, 484
  facilities, 2,309 road features and three district boundaries. The
  processed GeoJSON declares OGC:CRS84. That declaration describes the
  processed files, not an absent CRS declaration in the raw NIC GeoJSON.
- The processed vector layers have IDs in the checked primary-ID fields, but
  ID presence does not authenticate an ID namespace, issuer, or record
  lineage.
- The Phase 2A report documents aligned 30 m EPSG:32644 district DEM
  derivatives and masks unsupported source cells. Pithoragarh has 24,548
  unsupported cells masked and no valid pixels east of the locally verified
  raw-tile coverage edge.
- The original raw and processed files were not edited to produce this
  research note.

## Source-by-source findings

### Rural habitations and blocks

The manifest calls the habitation source “PMGSY Rural Habitations
(Uttarakhand)” and attributes it to the Ministry of Rural Development /
GeoSadak (OMMAS). Its download URL is a raw file in the third-party
`yashveeeeeeer/india-geodata` GitHub repository, not an official government
host. The local ZIP contains the PMGSY-named habitation shapefile components;
the manifest says the processed points and demographic attributes were
joined with PMGSY master data for block names. The block ZIP exists locally,
but the manifest does not give it a separate download URL or source version.

The ZIP’s shapefile projection sidecar declares WGS 84. That is useful local
format evidence, but the original NIC GeoJSON does not contain equivalent
embedded CRS evidence. No dated PMGSY export, original publication/update
date, official checksum, or copy of the applicable license notice was found.
The manifest’s `CC-BY-4.0 / GODL` label is consequently unverified for these
bytes. The 3,368 points are usable as the current project snapshot for
geographic inspection, subject to the nine boundary reviews and unknown
observation age. Do not describe them as a current or complete habitation
census.

### Healthcare facilities

The manifest attributes a national GeoJSON mirror to NIC HealthGIS / MoHFW.
Its exact recorded download URL is a GitHub release asset in the same
third-party repository. The local raw file contains 147,957 features and
does not declare a CRS. The manifest describes filtering it to the three
districts and combining it with a separate local PMGSY facilities ZIP.
That PMGSY ZIP is an input to the documented facility refinement, but its
own source URL, date/version and license are not recorded in the manifest.
The processed combined output is 484 rows, not 501.

The Phase 1 local replay reproduced 503 from an earlier deduplication recipe
and 484 from the refined recipe; neither explains the manifest’s 501.
The processed output has 172 NIC IDs and 316 PMGSY IDs; four records have
both identifiers. Some source-label and identifier combinations do not
agree. Keep the count discrepancy and per-record lineage unresolved. These
points are appropriate for locating records in the local snapshot, not for
asserting present-day operation, service capacity, official status, or
completeness. No current facility update date was established.

### Roads

The manifest attributes the road archive to the PMGSY GeoSadak DRRP network.
The recorded URL is a third-party GitHub release asset. The local ZIP has
WGS 84 projection sidecars, and the project description says it extracts
`Road_DRRP3.shp`, filters districts, and exports the processed
`roads_target_districts.geojson`. The processed file has 2,309 LineString
features with IDs under the project’s checked field. The road archive’s
survey date, update timestamp, official export identifier, license text and
publisher checksum are not locally evidenced. The manifest’s GODL statement
is not authenticated.

The data are appropriate as source geometries for map display and local
spatial inspection. They do not establish road condition, public access,
bridges, grade-separated crossings, connectivity, directionality or travel
speed. They are not a validated routing graph and should not support claims
of road distance or travel time.

### District boundaries

The manifest calls the boundary dataset “LGD District Administrative
Boundaries” and attributes it jointly to the Local Government Directory
(Ministry of Panchayati Raj) and Survey of India. The specific local Parquet
file is a third-party GitHub release asset. The manifest describes reading
Parquet WKB geometries, retaining LGD and Census 2011 codes, and exporting
the processed GeoJSON. The local IDs/attributes and CRS84 declaration are
verifiable as file contents; they do not prove the boundary geometry was
downloaded from either named agency. The manifest’s GODL claim, source
edition, effective date and geometry lineage remain unverified.

These boundaries are the project’s current spatial reference for its
out-of-boundary review, not a verified current legal boundary product. Nine
habitations are outside their assigned polygon (2 Chamoli, 2 Pithoragarh,
5 Rudraprayag); the source records remain unchanged.

### Copernicus elevation

The five local raw tiles have Copernicus-style GLO-30 one-degree names. The
manifest records the public S3 bucket base
`https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/` and says the
tiles were mosaicked and clipped. It does not record the exact object URLs
requested, request logs, product-package identifier, or release. The names,
GeoTIFF tiepoints/pixel scale, and the Phase 2A pixel-window validation
support the stated tile layout; local hashes do not independently prove
delivery from Copernicus.

Official Copernicus documentation says GLO-30 is a **digital surface model**
(buildings, vegetation and other reflective surfaces may remain), with
TanDEM-X acquisition mainly during 2011–2015 and older models used to fill
some gaps. The local tiles’ individual sensing dates and release are not
identified. Copernicus describes worldwide GLO-30 as freely available under
its user obligations and requires source/adaptation attribution. The
manifest’s generic “CC-BY-SA” description should not replace the
release-specific Copernicus terms or required attribution notice.

For public communication or distribution of the source product, Copernicus
specifies this notice:

> © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided
> under COPERNICUS by the European Union and ESA; all rights reserved

For adapted or modified data, its page specifies:

> produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus
> Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European
> Union and ESA; all rights reserved

The 30 m DEM derivatives are suitable for explicitly limited terrain
experiments where coverage is valid. They are not bare-earth elevation, and
they do not provide complete observed terrain outside the verified tile
footprint. The aggregate processed DEM predates Phase 2A and is not a
substitute for the validated district copies.
The local JSON sidecars and Phase 2A validation report describe processing
parameters and checks; they are project-authored records, not additional
publisher metadata. See
[`phase2a_validation_report.json`](../data/processed_phase2a/phase2a_validation_report.json).

### WorldPop

The local raw filename is `ind_pd_2020_1km.tif`, but the manifest points to a
third-party GitHub release, not a WorldPop download. The local TIFF has a
30-arc-second pixel scale, a geographic-looking tiepoint and nodata
`-99999`, but no embedded CRS GeoKey or DOI/version metadata. Phase 2A
records the crop/window relation to the processed raster; that does not
identify the upstream product or prove that the pixels are an unchanged
WorldPop release.

The cited official WorldPop record (DOI
`10.5258/SOTON/WP00647`) describes estimated people **per grid cell**, WGS84,
30 arc-seconds, and cites a 2018 product. Its page’s displayed production
date is malformed (`0018-02-01`). It does not verify that the local
2020-named file is that product. Therefore local vintage, exact interpretation
of values, and license remain unverified; the manifest’s CC-BY-4.0 claim is
not independently established for this copy. Do not treat the pixels as
habitation population counts or attach them to habitation records.

### Synthetic sample fixtures

The files under `data/sample` are generated by the local
`generate_fixtures.py` script for the synthetic/demo path. They have no
external geographic publisher and are not observations of the three real
districts. Their manifest identifies them as generated fixtures. Keep them
clearly separate from real-data maps and research claims.

## Official references checked

- Copernicus DEM product and user-obligation information:
  [Copernicus Data Space Ecosystem — Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).
- WorldPop product record:
  [WorldPop record, DOI 10.5258/SOTON/WP00647](https://hub.worldpop.org/geodata/summary?id=24777).
- Official portal hostnames checked but not retrievable in this environment:
  [PMGSY GeoSadak](https://geosadak-pmgsy.nic.in/) and
  [NIC HealthGIS](https://healthgis.mohfw.gov.in/). This check did not establish
  their current export mechanisms, product files, or terms of use.

The per-source URLs, local filenames, evidence, license claims, time coverage
and confidence/status are in
[`provenance_research_source_inventory.csv`](./provenance_research_source_inventory.csv).
The earlier row-level findings are in
[`data_issues.csv`](../data/provenance_audit_20261020_final/data_issues.csv),
[`facility_reconciliation.csv`](../data/provenance_audit_20261020_final/facility_reconciliation.csv)
and
[`habitation_boundary_reviews.csv`](../data/provenance_audit_20261020_final/habitation_boundary_reviews.csv).
