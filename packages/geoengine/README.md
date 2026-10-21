# HillCare GeoEngine

Core scientific and algorithmic engine for HillCare Access.

## Synthetic/demo algorithm capabilities

The capabilities below describe reusable algorithms exercised by the current
synthetic/demo pipeline. They do not imply that the processed real roads or
district datasets have been used for a real routed access result.

- **Tobler's Hiking Function**: Computes directional walking speed as a function of slope:
  $$v(S) = 6 \cdot \exp(-3.5 \cdot |S + 0.05|) \times \text{calibration}$$
- **16-Neighbour Connectivity**: 8 Queen moves + 8 Knight moves to suppress raster grid-alignment distortion.
- **Directional Cost Surface & Graph Inversion**: Calculates Habitation $\to$ Facility travel time using reverse-graph multi-source Dijkstra from health facilities in a single pass.
- **Surface Modifiers**: Modulate costs for footpaths, vehicle roads (hybrid mode), impassable rivers with bridge crossings, and seasonal SAR-detected disruptions.
- **Candidate Site Generation & Scoring**: Evaluates candidate locations by newly covered population within threshold $T$ ($\Delta \text{pop}$).
- **Facility Siting Optimizer**: Greedy submodular maximization $((1 - 1/e) \approx 63.2\%$ approximation guarantee) and exact solver.

## Real-data diagnostics

`hillcare_geoengine.real_data.load_real_district_data(data_dir, district)` loads
a district DEM from `data/processed_phase2a` and its habitation, facility,
road, and boundary features from `data/processed`. It carries explicit raster
georeferencing and validity masks, preserves source feature IDs/properties, and
returns boundary/geometry issues in `review_records`. This loader only prepares
inputs. `hillcare_geoengine.real_analysis` derives nodata-aware local slope and
an explicitly labeled uphill-equivalent Tobler proxy, reports provisional
2D road geometry intersections, and computes nearest-facility straight-line
distance in projected meters. These are diagnostics, not routed walking
distances or travel times. No road routing graph is implemented or claimed.
WorldPop density is not used as habitation population, and no facility
capacity/service availability is inferred.

From the project root, run the separate real-data workflow with
`python scripts\run_real_analysis.py`. It verifies the Phase 1 SHA-256
inventory and refuses to overwrite a non-empty output directory. Derived
reports and GeoTIFFs are written under `data\analysis_real_20261020` by
default.

The existing synthetic pipeline remains separate. To create a labeled
synthetic/demo JSON result without using the project database, run
`python scripts\run_synthetic_demo.py --district Rudraprayag --output <new-json-path>`.
When both modes have results, `scripts\compare_analysis_reports.py` creates a
side-by-side methodology report and deliberately does not compare their
incompatible metrics as equivalent measurements.

Install the `real-data` optional dependency extra to use this loader.
