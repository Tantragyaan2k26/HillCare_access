import {
  AssistantResponse,
  CandidateItem,
  CommunityReportCreate,
  CommunityReportReceipt,
  CommunityReportReview,
  CommunityStatus,
  FacilityItem,
  HabitationItem,
  RegionSummary,
  RealFeature,
  RealDistrictDataset,
  ScenarioCreateRequest,
  ScenarioResponse,
} from '../types';

const API_BASE = '/api/v1';
const realDistrictCache = new Map<string, RealDistrictDataset>();
const realRoadCache = new Map<string, RealFeature[]>();

async function parseResponse<T>(response: Response, message: string): Promise<T> {
  if (!response.ok) {
    const details = await response.json().catch(() => null);
    throw new Error(details?.detail || message);
  }
  return response.json() as Promise<T>;
}

export async function fetchRealDistrict(district: string, signal?: AbortSignal): Promise<RealDistrictDataset> {
  const cached = realDistrictCache.get(district);
  if (cached) return cached;
  const response = await fetch(
    `${API_BASE}/real-data/districts/${encodeURIComponent(district)}?include_roads=false`,
    { signal }
  );
  const data = await parseResponse<RealDistrictDataset>(response, `Failed to fetch real data for ${district}`);
  realDistrictCache.set(district, data);
  return data;
}

export async function fetchRealDistrictRoads(district: string, signal?: AbortSignal): Promise<RealFeature[]> {
  const cached = realRoadCache.get(district);
  if (cached) return cached;
  const response = await fetch(
    `${API_BASE}/real-data/districts/${encodeURIComponent(district)}/roads`,
    { signal }
  );
  const data = await parseResponse<{ features: RealFeature[] }>(
    response,
    `Failed to fetch road geometries for ${district}`
  );
  realRoadCache.set(district, data.features);
  return data.features;
}

export async function submitCommunityReport(payload: CommunityReportCreate): Promise<CommunityReportReceipt> {
  const response = await fetch(`${API_BASE}/community-reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse(response, 'Could not submit community report');
}

export async function fetchCommunityReportStatus(id: string): Promise<CommunityReportReceipt> {
  const response = await fetch(`${API_BASE}/community-reports/${encodeURIComponent(id)}`);
  return parseResponse(response, 'Could not load report status');
}

export async function fetchCommunityReports(token: string): Promise<CommunityReportReview[]> {
  const response = await fetch(`${API_BASE}/community-reports`, {
    headers: { 'X-Reviewer-Token': token },
  });
  return parseResponse(response, 'Could not load reviewer queue');
}

export async function reviewCommunityReport(
  id: string,
  token: string,
  status: CommunityStatus,
  note: string
): Promise<CommunityReportReceipt> {
  const response = await fetch(`${API_BASE}/community-reports/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'X-Reviewer-Token': token },
    body: JSON.stringify({ status, note }),
  });
  return parseResponse(response, 'Could not update community report');
}

export async function fetchRegions(level = 'district'): Promise<Array<{ id: number; name: string; level: string }>> {
  const res = await fetch(`${API_BASE}/regions?level=${level}`);
  if (!res.ok) throw new Error('Failed to fetch regions');
  return res.json();
}

export async function fetchRegionSummary(regionId: number): Promise<RegionSummary> {
  const res = await fetch(`${API_BASE}/regions/${regionId}/summary`);
  if (!res.ok) throw new Error(`Failed to fetch summary for region ${regionId}`);
  return res.json();
}

export async function fetchHabitations(
  districtId: number,
  limit = 200,
  threshold?: number,
  mode = 'walk'
): Promise<{ total_count: number; items: HabitationItem[] }> {
  let url = `${API_BASE}/habitations?district_id=${districtId}&limit=${limit}&mode=${mode}`;
  if (threshold !== undefined) {
    url += `&threshold=${threshold}`;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch habitations');
  return res.json();
}

export async function fetchFacilities(districtId: number, tier?: string): Promise<FacilityItem[]> {
  let url = `${API_BASE}/facilities?district_id=${districtId}`;
  if (tier && tier !== 'ALL') {
    url += `&tier=${tier}`;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch facilities');
  return res.json();
}

export async function fetchCandidates(district: string, objective = 'max_new_coverage'): Promise<CandidateItem[]> {
  const res = await fetch(`${API_BASE}/candidates?district=${district.toLowerCase()}&objective=${objective}`);
  if (!res.ok) throw new Error('Failed to fetch candidate sites');
  const data = await res.json();
  return data.candidates || [];
}

export async function createScenario(payload: ScenarioCreateRequest): Promise<ScenarioResponse> {
  const res = await fetch(`${API_BASE}/scenarios`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Role': 'planner',
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create scenario');
  return res.json();
}

export async function askAssistant(query: string, language: string, districtId?: number): Promise<AssistantResponse> {
  const res = await fetch(`${API_BASE}/assistant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, language, district_id: districtId }),
  });
  if (!res.ok) throw new Error('Assistant query failed');
  return res.json();
}
