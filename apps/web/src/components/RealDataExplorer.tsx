import React, { useEffect, useMemo, useRef, useState } from 'react';
import { LocateFixed, Minus, Plus, Search } from 'lucide-react';
import { fetchRealDistrict, fetchRealDistrictRoads } from '../services/api';
import { GeoGeometry, GeoPosition, RealDistrictDataset, RealFeature, RealLayerName } from '../types';

interface RealDataExplorerProps {
  district: string;
  coordinatePickMode?: boolean;
  onPickCoordinate?: (coordinate: { latitude: number; longitude: number }) => void;
}

type PickedFeature = { layer: RealLayerName; feature: RealFeature };
type ViewTransform = { scale: number; dx: number; dy: number };

const MAP_WIDTH = 1000;
const MAP_HEIGHT = 680;

function positionsIn(value: unknown): GeoPosition[] {
  if (!Array.isArray(value)) return [];
  if (typeof value[0] === 'number' && typeof value[1] === 'number') {
    return [value as GeoPosition];
  }
  return value.flatMap(positionsIn);
}

function featurePositions(feature: RealFeature): GeoPosition[] {
  return positionsIn(feature.geometry.coordinates);
}

function propertyText(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not provided';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function identity(feature: RealFeature, layer: RealLayerName): string {
  const properties = feature.properties;
  const raw = layer === 'habitations'
    ? properties.id
    : layer === 'facilities'
      ? properties.nic_source_id ?? properties.pmgsy_source_id ?? properties.facility_id ?? properties.id
      : layer === 'roads'
        ? properties.er_id
        : properties.lgd_code;
  return raw === undefined || raw === null ? 'No source ID' : String(raw);
}

function polygonCoordinates(geometry: GeoGeometry): GeoPosition[][][] {
  if (geometry.type === 'Polygon') return [geometry.coordinates];
  if (geometry.type === 'MultiPolygon') return geometry.coordinates;
  return [];
}

function simplifyLine(points: Array<[number, number]>, tolerance: number): Array<[number, number]> {
  if (points.length <= 2) return points;
  const keep = new Uint8Array(points.length);
  keep[0] = 1;
  keep[points.length - 1] = 1;
  const pending: Array<[number, number]> = [[0, points.length - 1]];
  const toleranceSquared = tolerance * tolerance;

  while (pending.length) {
    const segment = pending.pop();
    if (!segment) continue;
    const [start, end] = segment;
    const [startX, startY] = points[start];
    const [endX, endY] = points[end];
    const dx = endX - startX;
    const dy = endY - startY;
    const segmentLengthSquared = dx * dx + dy * dy;
    let farthestIndex = -1;
    let farthestDistanceSquared = toleranceSquared;

    for (let index = start + 1; index < end; index += 1) {
      const [x, y] = points[index];
      const projection = segmentLengthSquared === 0
        ? 0
        : Math.max(0, Math.min(1, ((x - startX) * dx + (y - startY) * dy) / segmentLengthSquared));
      const distanceX = x - (startX + projection * dx);
      const distanceY = y - (startY + projection * dy);
      const distanceSquared = distanceX * distanceX + distanceY * distanceY;
      if (distanceSquared > farthestDistanceSquared) {
        farthestDistanceSquared = distanceSquared;
        farthestIndex = index;
      }
    }

    if (farthestIndex >= 0) {
      keep[farthestIndex] = 1;
      pending.push([start, farthestIndex], [farthestIndex, end]);
    }
  }

  return points.filter((_, index) => keep[index] === 1);
}

export const RealDataExplorer: React.FC<RealDataExplorerProps> = ({
  district,
  coordinatePickMode = false,
  onPickCoordinate,
}) => {
  const [dataset, setDataset] = useState<RealDistrictDataset | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState<Record<RealLayerName, boolean>>({
    boundaries: true,
    habitations: true,
    facilities: true,
    roads: true,
  });
  const [selected, setSelected] = useState<PickedFeature | null>(null);
  const [search, setSearch] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [roadsLoading, setRoadsLoading] = useState(false);
  const [roadsError, setRoadsError] = useState('');
  const [roadsLoadedDistrict, setRoadsLoadedDistrict] = useState('');
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [view, setView] = useState<ViewTransform>({ scale: 1, dx: 0, dy: 0 });
  const svgRef = useRef<SVGSVGElement | null>(null);
  const roadsAbortRef = useRef<AbortController | null>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number; dx: number; dy: number; moved: boolean; beganOnFeature: boolean } | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    roadsAbortRef.current?.abort();
    setLoading(true);
    setError('');
    setDataset(null);
    setSelected(null);
    setVisible((current) => ({ ...current, roads: false }));
    setRoadsLoadedDistrict('');
    setRoadsError('');
    fetchRealDistrict(district, controller.signal)
      .then((loaded) => {
        if (active) {
          setDataset(loaded);
          setSelected(null);
          setSearch('');
          setView({ scale: 1, dx: 0, dy: 0 });
        }
      })
      .catch((reason: unknown) => {
        if (active && !(reason instanceof DOMException && reason.name === 'AbortError')) {
          setError(reason instanceof Error ? reason.message : 'Unable to load real district data.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
      roadsAbortRef.current?.abort();
    };
  }, [district, reloadKey]);

  const mapGeometry = useMemo(() => {
    if (!dataset) return null;
    const all = (['boundaries', 'habitations', 'facilities'] as RealLayerName[])
      .flatMap((layer) => dataset.layers[layer].flatMap(featurePositions));
    if (!all.length) return null;
    let minLat = Number.POSITIVE_INFINITY;
    let maxLat = Number.NEGATIVE_INFINITY;
    let minLon = Number.POSITIVE_INFINITY;
    let maxLon = Number.NEGATIVE_INFINITY;
    for (const [lon, lat] of all) {
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      minLon = Math.min(minLon, lon);
      maxLon = Math.max(maxLon, lon);
    }
    const latCenter = (minLat + maxLat) / 2;
    const cosLatitude = Math.cos((latCenter * Math.PI) / 180);
    const minX = minLon * cosLatitude;
    const maxX = maxLon * cosLatitude;
    const minY = minLat;
    const maxY = maxLat;
    const width = Math.max(maxX - minX, 0.0001);
    const height = Math.max(maxY - minY, 0.0001);
    const scale = Math.min((MAP_WIDTH - 70) / width, (MAP_HEIGHT - 70) / height);
    const offsetX = (MAP_WIDTH - width * scale) / 2;
    const offsetY = (MAP_HEIGHT - height * scale) / 2;
    return {
      project: ([lon, lat]: GeoPosition): [number, number] => [
        offsetX + (lon * cosLatitude - minX) * scale,
        MAP_HEIGHT - (offsetY + (lat - minY) * scale),
      ],
      unproject: (x: number, y: number): { latitude: number; longitude: number } => ({
        latitude: minY + (MAP_HEIGHT - y - offsetY) / scale,
        longitude: (minX + (x - offsetX) / scale) / cosLatitude,
      }),
    };
  }, [dataset]);

  const suggestions = useMemo(() => {
    if (!dataset || search.trim().length < 2) return [];
    const query = search.trim().toLowerCase();
    return (['habitations', 'facilities'] as const)
      .flatMap((layer) => dataset.layers[layer].map((feature) => ({ layer, feature })))
      .filter(({ feature }) => {
        const properties = feature.properties;
        return [properties.name, properties.id, properties.nic_source_id, properties.pmgsy_source_id, properties.facility_id]
          .some((value) => value !== undefined && String(value).toLowerCase().includes(query));
      })
      .slice(0, 8);
  }, [dataset, search]);

  const selectFeature = (layer: RealLayerName, feature: RealFeature) => {
    setSelected({ layer, feature });
    setDetailsOpen(true);
  };

  const toggleRoads = (enabled: boolean) => {
    setRoadsError('');
    if (!enabled) {
      roadsAbortRef.current?.abort();
      setRoadsLoading(false);
      setVisible((current) => ({ ...current, roads: false }));
      return;
    }
    if (roadsLoadedDistrict === district) {
      setVisible((current) => ({ ...current, roads: true }));
      return;
    }

    const controller = new AbortController();
    roadsAbortRef.current?.abort();
    roadsAbortRef.current = controller;
    setRoadsLoading(true);
    setVisible((current) => ({ ...current, roads: true }));
    fetchRealDistrictRoads(district, controller.signal)
      .then((roads) => {
        if (controller.signal.aborted) return;
        setDataset((current) => current?.district === district
          ? { ...current, layers: { ...current.layers, roads } }
          : current);
        setRoadsLoadedDistrict(district);
        setVisible((current) => ({ ...current, roads: true }));
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted && !(reason instanceof DOMException && reason.name === 'AbortError')) {
          setRoadsError(reason instanceof Error ? reason.message : 'Unable to load road geometries.');
          setVisible((current) => ({ ...current, roads: false }));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setRoadsLoading(false);
      });
  };

  const focusFeature = (layer: RealLayerName, feature: RealFeature) => {
    selectFeature(layer, feature);
    if (layer === 'roads' && roadsLoadedDistrict !== district) toggleRoads(true);
    setVisible((current) => ({ ...current, [layer]: true }));
    const coordinates = featurePositions(feature);
    if (coordinates.length && mapGeometry) {
      const [x, y] = mapGeometry.project(coordinates[0]);
      setView((current) => ({
        ...current,
        dx: MAP_WIDTH / 2 - x * current.scale,
        dy: MAP_HEIGHT / 2 - y * current.scale,
      }));
    }
    setSearch('');
  };

  const localPoint = (event: { clientX: number; clientY: number }): [number, number] => {
    const svg = svgRef.current;
    if (!svg) return [0, 0];
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const transformed = point.matrixTransform(svg.getScreenCTM()?.inverse());
    return [transformed.x, transformed.y];
  };

  const onPointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    const [x, y] = localPoint(event);
    dragRef.current = {
      pointerId: event.pointerId,
      x,
      y,
      dx: view.dx,
      dy: view.dy,
      moved: false,
      beganOnFeature: !coordinatePickMode
        && (event.target as Element).closest('[data-map-feature="true"]') !== null,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const [x, y] = localPoint(event);
    const dx = x - drag.x;
    const dy = y - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    if (drag.moved) setView((current) => ({ ...current, dx: drag.dx + dx, dy: drag.dy + dy }));
  };

  const onPointerUp = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (!drag.moved && !drag.beganOnFeature && coordinatePickMode && mapGeometry && onPickCoordinate) {
      const [x, y] = localPoint(event);
      onPickCoordinate(mapGeometry.unproject((x - view.dx) / view.scale, (y - view.dy) / view.scale));
    }
    dragRef.current = null;
  };

  const adjustZoom = (factor: number, anchorX = MAP_WIDTH / 2, anchorY = MAP_HEIGHT / 2) => {
    setView((current) => {
      const scale = Math.min(20, Math.max(0.7, current.scale * factor));
      const ratio = scale / current.scale;
      return {
        scale,
        dx: anchorX - (anchorX - current.dx) * ratio,
        dy: anchorY - (anchorY - current.dy) * ratio,
      };
    });
  };

  const renderGeometry = (geometry: GeoGeometry): string => {
    if (!mapGeometry) return '';
    const lines: GeoPosition[][] = geometry.type === 'LineString'
      ? [geometry.coordinates]
      : geometry.type === 'MultiLineString'
        ? geometry.coordinates
        : [];
    const displayScale = (svgRef.current?.getBoundingClientRect().width ?? MAP_WIDTH) / MAP_WIDTH;
    const tolerance = Math.max(0.65, 1.1 / (displayScale * view.scale));
    return lines.map((line) => simplifyLine(line.map(mapGeometry.project), tolerance)
      .map(([x, y], index) => `${index === 0 ? 'M' : 'L'} ${x} ${y}`).join(' ')).join(' ');
  };

  if (loading) return <div className="real-map-loading" role="status" aria-live="polite">
    <span className="real-loading-spinner" aria-hidden="true" />
    <span>Loading {district} source features…</span>
  </div>;
  if (error || !dataset || !mapGeometry) {
    return <div role="alert" className="m-6 rounded-xl border border-rose-800 bg-rose-950/40 p-5 text-rose-200">
      <p>Real-data map unavailable: {error || 'The district dataset is empty.'}</p>
      <button className="real-tool-button" onClick={() => setReloadKey((key) => key + 1)}>Retry loading map</button>
    </div>;
  }

  const selectedProperties = selected?.feature.properties ?? {};
  const selectedNearest = selected?.layer === 'habitations' ? selected.feature.nearest_facility : null;

  return (
    <section className="real-map-page">
      <div className="real-map-heading">
        <div>
          <p className="real-eyebrow">REAL DATA · SOURCE GEOMETRIES</p>
          <h1>{district} district map</h1>
          <p>Processed local records in {dataset.crs}. No modeled access time or road routing is shown.</p>
        </div>
        <span className="real-status">Publisher attribution not independently verified per record</span>
      </div>

      <div className="real-stats" aria-label={`${district} source dataset counts`}>
        <div><strong>{dataset.counts.habitations.toLocaleString()}</strong><span>Habitations</span></div>
        <div><strong>{dataset.counts.facilities.toLocaleString()}</strong><span>Healthcare facilities</span></div>
        <div><strong>{dataset.counts.road_segments.toLocaleString()}</strong><span>Road geometries</span></div>
        <div><strong>{dataset.counts.habitations_outside_assigned_boundary}</strong><span>Habitations flagged for boundary review</span></div>
      </div>

      <div className="real-map-layout">
        <div className="real-map-column">
          <div className="real-map-toolbar">
            <label className="real-search">
              <Search size={16} aria-hidden="true" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search name or source ID"
                aria-label="Search real map features by name or source ID"
                autoComplete="off"
              />
              {suggestions.length > 0 && <span className="real-search-results">
                {suggestions.map(({ layer, feature }) => (
                  <button key={`${layer}-${identity(feature, layer)}`} onClick={() => focusFeature(layer, feature)}>
                    <b>{layer === 'habitations' ? 'Habitation' : 'Facility'}</b>
                    {String(feature.properties.name ?? 'Unnamed')} · ID {identity(feature, layer)}
                  </button>
                ))}
              </span>}
            </label>
            <button className="real-tool-button" onClick={() => setView({ scale: 1, dx: 0, dy: 0 })} title="Reset map view">
              <LocateFixed size={16} /> Fit
            </button>
            <button className="real-tool-button" onClick={() => adjustZoom(1.25)} aria-label="Zoom in"><Plus size={16} /></button>
            <button className="real-tool-button" onClick={() => adjustZoom(0.8)} aria-label="Zoom out"><Minus size={16} /></button>
            <button
              type="button"
              className="real-tool-button real-detail-toggle"
              aria-expanded={detailsOpen}
              onClick={() => setDetailsOpen((open) => !open)}
            >
              {selected ? `Details · ${propertyText(selected.feature.properties.name ?? selected.feature.properties.district_name)}` : 'Feature details'}
            </button>
          </div>
          {roadsLoading && <div className="real-map-inline-status" role="status">Loading full road geometries…</div>}
          {roadsError && <div className="real-map-inline-error" role="alert">
            Road layer unavailable: {roadsError}
            <button className="real-tool-button" onClick={() => toggleRoads(true)}>Retry roads</button>
          </div>}
          {coordinatePickMode && <div className="real-pick-notice">Click an approximate location on the map to attach coordinates to your community report.</div>}
          <svg
            ref={svgRef}
            className={`real-map-canvas${coordinatePickMode ? ' real-map-pick-mode' : ''}`}
            viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
            role="img"
            aria-label={`${district} map showing source habitations, health facilities, roads, and district boundary`}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={() => { dragRef.current = null; }}
            onWheel={(event) => {
              event.preventDefault();
              const [x, y] = localPoint(event);
              adjustZoom(event.deltaY < 0 ? 1.12 : 0.89, x, y);
            }}
          >
            <rect width={MAP_WIDTH} height={MAP_HEIGHT} fill="#0c1720" />
            <g transform={`translate(${view.dx} ${view.dy}) scale(${view.scale})`}>
              {visible.boundaries && dataset.layers.boundaries.map((feature, index) => (
                <g key={`boundary-${index}`}>
                  {polygonCoordinates(feature.geometry).map((polygon, polygonIndex) => (
                    <path
                      key={polygonIndex}
                      d={polygon.map((ring) => `M ${ring.map((position) => mapGeometry.project(position).join(' ')).join(' L ')} Z`).join(' ')}
                      fill="#193d3b"
                      fillOpacity="0.33"
                      stroke="#79a99a"
                      strokeWidth="1.7"
                      vectorEffect="non-scaling-stroke"
                      onClick={(event) => { event.stopPropagation(); selectFeature('boundaries', feature); }}
                      data-map-feature="true"
                    />
                  ))}
                </g>
              ))}
              {visible.roads && dataset.layers.roads.map((feature, index) => {
                if (feature.geometry.type !== 'LineString' && feature.geometry.type !== 'MultiLineString') return null;
                return <path
                  key={`road-${index}`}
                  d={renderGeometry(feature.geometry)}
                  fill="none"
                  stroke="#9aa5a4"
                  strokeOpacity="0.48"
                  strokeWidth="1"
                  vectorEffect="non-scaling-stroke"
                  onClick={(event) => { event.stopPropagation(); selectFeature('roads', feature); }}
                  data-map-feature="true"
                />;
              })}
              {visible.habitations && dataset.layers.habitations.map((feature, index) => {
                if (feature.geometry.type !== 'Point') return null;
                const [x, y] = mapGeometry.project(feature.geometry.coordinates);
                return <circle
                  key={`habitation-${index}`}
                  cx={x}
                  cy={y}
                  r={selected?.feature === feature ? 5.5 : 3.2}
                  fill={selected?.feature === feature ? '#f7d777' : '#42c8a4'}
                  stroke="#082b27"
                  strokeWidth="0.7"
                  vectorEffect="non-scaling-stroke"
                  onClick={(event) => { event.stopPropagation(); selectFeature('habitations', feature); }}
                  data-map-feature="true"
                />;
              })}
              {visible.facilities && dataset.layers.facilities.map((feature, index) => {
                if (feature.geometry.type !== 'Point') return null;
                const [x, y] = mapGeometry.project(feature.geometry.coordinates);
                return <path
                  key={`facility-${index}`}
                  d={`M ${x} ${y - 7} L ${x + 6} ${y + 5} L ${x - 6} ${y + 5} Z`}
                  fill={selected?.feature === feature ? '#ffe287' : '#ff8a71'}
                  stroke="#54251f"
                  strokeWidth="1"
                  vectorEffect="non-scaling-stroke"
                  onClick={(event) => { event.stopPropagation(); selectFeature('facilities', feature); }}
                  data-map-feature="true"
                />;
              })}
            </g>
            <text x="18" y="30" fill="#d3dfdd" fontSize="15" fontWeight="600">{district}</text>
            <text x="18" y="654" fill="#8ca19e" fontSize="12">Source geometries · drag to pan · scroll to zoom</text>
          </svg>
          <div className="real-legend">
            {(['boundaries', 'habitations', 'facilities', 'roads'] as RealLayerName[]).map((layer) => (
              <label key={layer}>
                <input
                  type="checkbox"
                  checked={visible[layer]}
                  onChange={(event) => layer === 'roads'
                    ? toggleRoads(event.target.checked)
                    : setVisible((current) => ({ ...current, [layer]: event.target.checked }))}
                />
                <span className={`real-legend-mark ${layer}`} />
                {layer === 'boundaries' ? 'District boundary' : layer === 'habitations' ? 'Habitation' : layer === 'facilities' ? 'Health facility' : 'Road geometry'}
              </label>
            ))}
          </div>
        </div>

        <aside className={`real-detail-panel${detailsOpen ? ' is-open' : ''}`} aria-label="Selected feature details">
          <button type="button" className="real-detail-close" onClick={() => setDetailsOpen(false)}>Close details</button>
          {!selected ? (
            <div className="real-empty-detail">
              <span className="real-detail-kicker">FEATURE DETAILS</span>
              <h2>Select a map feature</h2>
              <p>Click a point, facility, road or district boundary to inspect the stored attributes and source IDs.</p>
              <p className="real-data-caution">Every mapped feature is shown from the processed source dataset. Provider attribution and individual record authenticity are not independently verified.</p>
              <div className="real-source-note"><b>Layers</b><br />Green circles · habitations<br />Coral triangles · healthcare facilities<br />Grey lines · source road geometries</div>
            </div>
          ) : (
            <div className="real-feature-detail">
              <span className="real-detail-kicker">{selected.layer.replace('_', ' ').toUpperCase()}</span>
              <h2>{propertyText(selectedProperties.name ?? selectedProperties.district_name)}</h2>
              <dl>
                <dt>Source ID</dt><dd>{identity(selected.feature, selected.layer)}</dd>
                <dt>Source attribution</dt><dd>{propertyText(selectedProperties.source ?? dataset.provenance[selected.layer])}</dd>
                <dt>Verification</dt><dd>Attribution only; record not independently verified</dd>
                {selected.feature.review_flags?.map((flag) => (
                  <React.Fragment key={flag}><dt>Data review</dt><dd>{flag}</dd></React.Fragment>
                ))}
                {Object.entries(selectedProperties).slice(0, 24).map(([key, value]) => (
                  <React.Fragment key={key}><dt>{key.replace(/_/g, ' ')}</dt><dd>{propertyText(value)}</dd></React.Fragment>
                ))}
                {selected.feature.geometry.type === 'Point' && <>
                  <dt>Longitude</dt><dd>{selected.feature.geometry.coordinates[0].toFixed(6)}</dd>
                  <dt>Latitude</dt><dd>{selected.feature.geometry.coordinates[1].toFixed(6)}</dd>
                </>}
              </dl>
              {selectedNearest && <div className="real-nearest">
                <b>Nearest recorded facility</b>
                <strong>{selectedNearest.name || 'Unnamed facility'}</strong>
                <span>{selectedNearest.tier || 'Tier not provided'} · source ID {selectedNearest.source_id ?? 'not provided'}</span>
                <strong>{selectedNearest.distance_km.toFixed(3)} km straight-line</strong>
                <small>Great-circle proximity from the recorded coordinates. Not road distance, walking distance, or travel time.</small>
              </div>}
            </div>
          )}
        </aside>
      </div>

      <p className="real-methodology">
        Nearest-facility distance uses a spherical great-circle calculation (mean Earth radius 6,371.0088 km)
        against the district’s recorded facility points. It is a geographic proximity measure, not road-network
        routing or travel time. No facility capacity or availability is inferred. Road lines are displayed as
        source geometries only; connectivity and routing are not validated.
      </p>
    </section>
  );
};
