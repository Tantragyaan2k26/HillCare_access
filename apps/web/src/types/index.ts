export type TravelMode = 'walk' | 'hybrid';
export type FacilityTier = 'ALL' | 'DH' | 'CHC' | 'PHC' | 'HWC';
export type Objective = 'max_new_coverage' | 'equity_weighted' | 'min_mean_time';

export interface TravelTimeRange {
  base: number;
  low: number;
  high: number;
}

export interface NearestFacility {
  id: number;
  name: string;
  tier: string;
}

export interface HabitationItem {
  id: number;
  name: string;
  block?: string;
  lat: number;
  lon: number;
  elevation_m: number;
  population: number;
  sc_pct: number;
  st_pct: number;
  travel_time_min: TravelTimeRange;
  hybrid_time_min: number;
  nearest_facility?: NearestFacility;
  underserved: Record<string, boolean>;
  quality_flags: string[];
}

export interface FacilityItem {
  id: number;
  name: string;
  tier: string;
  lat: number;
  lon: number;
  elevation_m: number;
  region_id: number;
  is_functional: boolean;
  doctor_count: number;
  bed_count: number;
}

export interface CandidateItem {
  id: number;
  rank: number;
  lat: number;
  lon: number;
  gain_pop: number;
  mean_time_delta: number;
  equity_score: number;
  feasibility?: {
    notes?: string[];
    grid?: [number, number];
  };
}

export interface RegionSummary {
  region_id: number;
  region_name: string;
  level: string;
  total_population: number;
  total_habitations: number;
  mean_travel_time_min: number;
  median_travel_time_min: number;
  underserved_pct_30min: number;
  underserved_pct_60min: number;
  underserved_pct_90min: number;
  functional_facilities_count: number;
}

export interface AssistantCitation {
  source_title: string;
  section?: string;
  quote: string;
  uri?: string;
}

export interface AssistantResponse {
  query: string;
  language: string;
  answer: string;
  citations: AssistantCitation[];
  tool_calls_executed: string[];
}

export interface ScenarioCreateRequest {
  name: string;
  region_id: number;
  tier: string;
  threshold_min: number;
  mode: string;
  objective: string;
  k: number;
  calibration: number;
  hypothetical_facility_lat?: number;
  hypothetical_facility_lon?: number;
}

export interface ScenarioResponse {
  id: string;
  owner_id: string;
  name: string;
  status: string;
  params: Record<string, any>;
  run_id?: string;
  result?: {
    total_habitations: number;
    total_population: number;
    underserved_habitations_60min: number;
    underserved_population_60min: number;
    pct_underserved_60min: number;
    top_candidates_selected: number;
    total_newly_covered_population: number;
  };
}

export type RealLayerName = 'boundaries' | 'habitations' | 'facilities' | 'roads';

export type GeoPosition = [number, number, ...number[]];

export type GeoGeometry =
  | { type: 'Point'; coordinates: GeoPosition }
  | { type: 'LineString'; coordinates: GeoPosition[] }
  | { type: 'MultiLineString'; coordinates: GeoPosition[][] }
  | { type: 'Polygon'; coordinates: GeoPosition[][] }
  | { type: 'MultiPolygon'; coordinates: GeoPosition[][][] };

export interface RealFeature {
  type: 'Feature';
  id?: number | string;
  geometry: GeoGeometry;
  properties: Record<string, unknown>;
  review_flags?: string[];
  nearest_facility?: {
    source_id: string | number | null;
    facility_id: string | number | null;
    name: string | null;
    tier: string | null;
    distance_km: number;
    distance_method: string;
  } | null;
}

export interface RealDistrictDataset {
  analysis_mode: 'real_data_map';
  district: string;
  crs: string;
  counts: {
    habitations: number;
    facilities: number;
    road_segments: number;
    district_boundaries: number;
    habitations_outside_assigned_boundary: number;
  };
  methodology: {
    source_attribution: string;
    habitation_population: string;
    nearest_facility: string;
    road_routing: boolean;
    worldpop_population_assignment: boolean;
  };
  layers: Record<RealLayerName, RealFeature[]>;
  provenance: Record<string, string>;
}

export type CommunityCategory =
  | 'missing_habitation'
  | 'missing_facility'
  | 'road_update'
  | 'correction'
  | 'facility_closure'
  | 'access_barrier';

export type CommunityStatus =
  | 'pending'
  | 'community-confirmed'
  | 'officially-confirmed'
  | 'rejected'
  | 'needs-recheck';

export interface CommunityReportCreate {
  category: CommunityCategory;
  district: string;
  latitude: number;
  longitude: number;
  subject: string;
  description: string;
  evidence_source: string;
  evidence_url?: string;
  observed_on?: string;
  based_on_report_id?: string;
}

export interface CommunityReportReceipt {
  id: string;
  status: CommunityStatus;
  district: string;
  category: CommunityCategory;
  submitted_at: string;
  observed_on: string | null;
}

export interface CommunityReportReview extends CommunityReportReceipt {
  latitude: number;
  longitude: number;
  subject: string;
  description: string;
  evidence_source: string;
  evidence_url: string | null;
  based_on_report_id: string | null;
}
