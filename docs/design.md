# HillCare Access: System Design Document
Slope-adjusted health-facility access analysis for hilly districts of India. Version 1.1 (adds JEPA, RAG, SAR and remote sensing), October 2026. Pilot region: Uttarakhand (Pithoragarh, Chamoli, Rudraprayag).

## 1. Executive Summary
The problem. Health-access planning in hill regions usually uses straight-line distance to the nearest Primary Health Centre (PHC). In the mountains this is badly misleading: a village 3 km away across a ridge and gorge is far harder to reach than one 3 km along a gentle valley.
The idea. HillCare Access estimates realistic walking time from every habitation to the nearest functional health facility using Tobler's Hiking Function on a terrain model (DEM), combined with trails, roads and river barriers. It then (a) flags underserved habitations, and (b) uses an optimisation algorithm to recommend where one new health centre would newly cover the most people.
The product. A web application with a public interactive map and dashboards, a secure planner workspace, and a REST API, backed by an offline geospatial computation pipeline on AWS.
The AI and earth-observation layer (v1.1). The terrain model is now fed by satellite data. Sentinel-1 SAR (which sees through monsoon cloud) and optical imagery are processed into trail, settlement, landslide and river-crossing layers. A JEPA-style self-supervised encoder learns reusable image representations from unlabeled Himalayan scenes, so these layers need few labels. A RAG assistant lets planners ask questions in English or Hindi and get answers grounded in health-norm documents and the system's own results, with citations. Neither layer replaces the Tobler core: both are optional, versioned, benchmarked against simple baselines, and shown with confidence scores.

### Who it is for
| Audience | What they get |
| :--- | :--- |
| District health officers, planners | Maps of underserved habitations, ranked candidate sites, exportable reports |
| Researchers, NGOs | Open data, API, reproducible methodology |
| Citizens, journalists | Public map showing how far each village really is from care |
| Developers | A clear, modular codebase specified in this document |

What it claims and does not claim. It measures geographic accessibility, not utilisation or unmet need. Results are model estimates with stated uncertainty.

---

## 2. Goals, Non-Goals and Requirements

### 2.1 Goals
1. Compute slope-adjusted walking time from each habitation to the nearest facility.
2. Identify underserved habitations at configurable thresholds (default 30, 60, 90 minutes).
3. Recommend the best site for one new facility (extendable to k facilities).
4. Present results visually, with transparent methods and uncertainty.
5. Be reproducible: the same inputs and parameters always yield the same outputs.

### 2.2 Non-Goals (v1)
- Real-time navigation or turn-by-turn routing.
- Clinical quality, staffing adequacy or utilisation modelling.
- Individual patient data. The system holds no personal health data.
- Whole-country coverage (v1 is district and state scale: Uttarakhand pilot).

### 2.3 Functional Requirements
| ID | Requirement |
| :--- | :--- |
| F1 | Ingest habitations, facilities, DEM, roads, trails, rivers and bridges |
| F2 | Compute per-habitation travel time to the nearest facility (walk-only and hybrid walk plus vehicle) |
| F3 | Classify habitations as served or underserved per threshold |
| F4 | Generate feasible candidate sites and rank by newly covered population |
| F5 | Provide equity-weighted and mean-travel-time objectives as alternatives |
| F6 | Interactive map, filters, comparison of scenarios, CSV/GeoJSON/PDF export |
| F7 | Planner users can create scenarios (add a hypothetical facility, change thresholds) |
| F8 | Public read-only API with documented endpoints |
| F9 | Ingest and process Sentinel-1 SAR and Sentinel-2 optical imagery (via STAC catalogues) into analysis-ready layers |
| F10 | Derive trail, road, settlement, river-crossing and landslide layers with confidence scores and a human review queue |
| F11 | Compute seasonal travel times (dry season vs monsoon) using SAR-detected disruptions |
| F12 | Train, evaluate, register and version a self-supervised (JEPA-style) encoder and its downstream task heads |
| F13 | Provide a RAG assistant (English and Hindi) grounded in documents and live results, always with citations |

---

## 3. Methodology (the Scientific Core)

### 3.1 Tobler's Hiking Function
Walking speed $v$ in km/h for slope $S$ (rise over run, so 0.1 means 10%):
$$v = 6 \cdot \exp(-3.5 \cdot |S + 0.05|)$$
Peak speed is ~5.037 km/h at a slight downhill ($S = -0.05$). Speed falls steeply on steep grades. The function is asymmetric, so travel time from A to B differs from B to A. Time for a grid edge = 3D distance / speed.

### 3.2 Cost surface and directionality
- Graph from DEM raster: Each cell connects to 16 neighbours (8 queen plus 8 knight moves) to mitigate grid-directional bias.
- Edge slope uses 3D distance: $\Delta z / \text{horizontal distance}$.
- Direction matters: The patient travels from habitation to facility. To compute nearest-facility time for all habitations in one pass, run multi-source Dijkstra from the facilities on the reversed graph (reversing every edge's slope sign), so values represent habitation-to-facility time.
- Emergency and carried-patient mode: multiply walking time by a configurable factor (default 2.0).

### 3.3 Modifiers layered on the terrain
| Layer | Treatment |
| :--- | :--- |
| Roads (motorable) | Vehicle speed by class (e.g., 20 km/h hill road); hybrid mode only |
| Trails and footpaths | Speed multiplier (default 1.25) because of surface quality, and lower penalty on steep slopes |
| Rivers | Impassable barrier cells except at known bridges and ford points |
| Forest, snow, landslide zones | Optional penalty multiplier (default 1.0, configurable) |
| Calibration factor | Single scalar fitted to field or GPS reference times (default 1.0; low 0.8, high 1.2) |

### 3.4 Two travel modes
- **Walk-only**: pure terrain walking. Measures physical isolation.
- **Hybrid**: walk to the nearest motorable road, then vehicle to the facility, with a fixed wait penalty (default 20 min).

### 3.5 Underserved definition
A habitation is underserved at threshold $T$ if its modelled time to the nearest functional facility of the chosen tier exceeds $T$ (defaults: 30, 60, 90 minutes).

### 3.6 Siting algorithm: maximal coverage with feasibility
$$\text{gain}(c) = \sum_{h \in \text{reachable within } T, h \text{ underserved}} \text{population}(h)$$
Only newly covered population counts.

---

## 4. System Architecture
```
                           USERS (public, planners, admins)
                                        |
                                +-------v--------+
                                |  Route 53 DNS  |
                                +-------+--------+
                                        |
                  +---------------------v----------------------+
                  |  CloudFront CDN  +  AWS WAF (rate rules)   |
                  +-----+-----------------------------+--------+
                        |                             |
          static + tiles (cached)              /api/* (dynamic)
                        |                             |
              +---------v--------+          +---------v----------+
              |  S3: web bundle  |          |  ALB  ->  ECS      |
              |  S3: PMTiles,    |          |  Fargate: FastAPI  |
              |  COG rasters     |          +----+----------+----+
              +------------------+               |          |
                                       +---------v--+   +---v-----------+
                                       | RDS Postgres|   | ElastiCache   |
                                       | + PostGIS   |   | Redis (cache, |
                                       +-----^-------+   | rate limits)  |
                                             |           +---------------+
                                             |
   +-----------------------------------------+------------------------+
   |                 COMPUTE PLANE (offline / async)                  |
   |  SQS queue -> AWS Batch (Fargate/EC2 Spot) workers:              |
   |    ingest -> cost surface -> travel times -> underserved ->      |
   |    candidates -> optimiser -> tile build -> write to RDS + S3    |
   |  Step Functions orchestrates the full pipeline                   |
   +------------------------------------------------------------------+
```
