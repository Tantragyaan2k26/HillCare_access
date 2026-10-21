import React, { useState, useMemo } from 'react';
import {
  Compass,
  Layers,
  Sliders,
  AlertTriangle,
  Info,
  Building2,
  MapPin,
  Sparkles,
  CloudRain,
  Eye,
  Filter,
} from 'lucide-react';
import { TranslationDict } from '../i18n/translations';
import {
  CandidateItem,
  FacilityItem,
  FacilityTier,
  HabitationItem,
  Objective,
  TravelMode,
} from '../types';

interface MapExplorerProps {
  t: TranslationDict;
  habitations: HabitationItem[];
  facilities: FacilityItem[];
  candidates: CandidateItem[];
  selectedDistrictName: string;
  onSelectHabitation: (hab: HabitationItem) => void;
  onSelectCandidate: (cand: CandidateItem) => void;
}

export const MapExplorer: React.FC<MapExplorerProps> = ({
  t,
  habitations,
  facilities,
  candidates,
  selectedDistrictName,
  onSelectHabitation,
  onSelectCandidate,
}) => {
  // Map filter states
  const [selectedTier, setSelectedTier] = useState<FacilityTier>('PHC');
  const [thresholdMin, setThresholdMin] = useState<number>(60);
  const [travelMode, setTravelMode] = useState<TravelMode>('walk');
  const [objective, setObjective] = useState<Objective>('max_new_coverage');
  const [showMonsoonDisruptions, setShowMonsoonDisruptions] = useState<boolean>(false);
  const [showContours, setShowContours] = useState<boolean>(true);
  const [hoveredHab, setHoveredHab] = useState<HabitationItem | null>(null);

  // Compute map bounds to fit points dynamically
  const bounds = useMemo(() => {
    if (habitations.length === 0) {
      return { minLat: 29.5, maxLat: 30.5, minLon: 79.0, maxLon: 80.5 };
    }
    const lats = habitations.map((h) => h.lat);
    const lons = habitations.map((h) => h.lon);
    return {
      minLat: Math.min(...lats) - 0.05,
      maxLat: Math.max(...lats) + 0.05,
      minLon: Math.min(...lons) - 0.05,
      maxLon: Math.max(...lons) + 0.05,
    };
  }, [habitations]);

  // Project lat/lon to SVG canvas coordinate space (width 800, height 550)
  const mapWidth = 800;
  const mapHeight = 550;

  const project = (lat: number, lon: number): [number, number] => {
    const latSpan = bounds.maxLat - bounds.minLat || 1.0;
    const lonSpan = bounds.maxLon - bounds.minLon || 1.0;
    const x = ((lon - bounds.minLon) / lonSpan) * (mapWidth - 100) + 50;
    // Invert y because SVG y goes top-down
    const y = (1.0 - (lat - bounds.minLat) / latSpan) * (mapHeight - 100) + 50;
    return [x, y];
  };

  // Color coding by travel time
  const getTravelTimeColor = (minutes: number) => {
    if (minutes <= 30) return '#22c55e'; // Green - compliant with norm
    if (minutes <= 60) return '#eab308'; // Yellow - moderate
    if (minutes <= 90) return '#f97316'; // Orange - high isolation
    return '#ef4444'; // Red - critical underserved
  };

  // Filter facilities by tier
  const filteredFacilities = useMemo(() => {
    if (selectedTier === 'ALL') return facilities;
    if (selectedTier === 'PHC') return facilities.filter((f) => ['DH', 'CHC', 'PHC'].includes(f.tier));
    if (selectedTier === 'CHC') return facilities.filter((f) => ['DH', 'CHC'].includes(f.tier));
    return facilities.filter((f) => f.tier === selectedTier);
  }, [facilities, selectedTier]);

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100vh-4rem)] bg-slate-950 overflow-hidden">
      {/* Left Control & Filter Sidebar */}
      <div className="w-full lg:w-96 bg-slate-900 border-r border-slate-800 p-5 overflow-y-auto space-y-5 flex-shrink-0">
        <div>
          <div className="flex items-center space-x-2 text-emerald-400 font-semibold text-sm uppercase tracking-wider mb-1">
            <Sliders className="w-4 h-4" />
            <span>Map Controls & Filters</span>
          </div>
          <h2 className="text-xl font-bold text-white">{selectedDistrictName} Accessibility</h2>
          <p className="text-xs text-slate-400 mt-1">Slope-adjusted walking model (Tobler Hiking Function)</p>
        </div>

        {/* Travel Mode Toggle */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center justify-between">
            <span>{t.filterMode}</span>
            <span className="text-emerald-400 text-[10px]">Asymmetric 3D</span>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setTravelMode('walk')}
              className={`px-3 py-2 text-xs font-medium rounded-lg border transition-all text-left ${
                travelMode === 'walk'
                  ? 'bg-emerald-950 border-emerald-500 text-emerald-200'
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="font-semibold text-white">🚶 Pure Walking</div>
              <div className="text-[10px] text-slate-400 mt-0.5">Physical isolation</div>
            </button>
            <button
              onClick={() => setTravelMode('hybrid')}
              className={`px-3 py-2 text-xs font-medium rounded-lg border transition-all text-left ${
                travelMode === 'hybrid'
                  ? 'bg-emerald-950 border-emerald-500 text-emerald-200'
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="font-semibold text-white">🚙 Hybrid Mode</div>
              <div className="text-[10px] text-slate-400 mt-0.5">Walk + Hill Road</div>
            </button>
          </div>
        </div>

        {/* Walking Threshold Slider */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              {t.filterThreshold}: <span className="text-emerald-400 font-bold text-sm">{thresholdMin} min</span>
            </label>
            <div className="flex space-x-1">
              {[30, 60, 90].map((th) => (
                <button
                  key={th}
                  onClick={() => setThresholdMin(th)}
                  className={`px-2 py-0.5 text-[11px] rounded font-medium ${
                    thresholdMin === th ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {th}m
                </button>
              ))}
            </div>
          </div>
          <input
            type="range"
            min={15}
            max={120}
            step={5}
            value={thresholdMin}
            onChange={(e) => setThresholdMin(Number(e.target.value))}
            className="w-full accent-emerald-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-slate-400">
            <span>15m (Sub-centre)</span>
            <span>60m (PHC standard)</span>
            <span>120m (Remote)</span>
          </div>
        </div>

        {/* Facility Tier Filter */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">{t.filterTier}</label>
          <select
            value={selectedTier}
            onChange={(e) => setSelectedTier(e.target.value as FacilityTier)}
            className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:ring-emerald-500 focus:border-emerald-500"
          >
            <option value="PHC">Primary Health Centres (PHC + CHC + DH)</option>
            <option value="HWC">Health & Wellness Centres (HWC / Sub-Centres)</option>
            <option value="CHC">Community Health Centres (CHC + DH)</option>
            <option value="DH">District Hospital Only</option>
            <option value="ALL">All Health Tiers Combined</option>
          </select>
        </div>

        {/* Earth Observation (v1.1) Layer Toggles */}
        <div className="space-y-2 pt-2 border-t border-slate-800">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-300 uppercase tracking-wider">
            <span className="flex items-center space-x-1.5">
              <CloudRain className="w-3.5 h-3.5 text-blue-400" />
              <span>SAR Earth Observation (v1.1)</span>
            </span>
            <span className="px-1.5 py-0.2 bg-blue-950 text-blue-400 border border-blue-800 rounded text-[9px]">Sentinel-1</span>
          </div>

          <label className="flex items-center justify-between p-2.5 bg-slate-800/70 border border-slate-700/60 rounded-lg cursor-pointer hover:bg-slate-800">
            <div className="text-xs">
              <div className="font-medium text-slate-200">Monsoon Landslide Mask</div>
              <div className="text-[10px] text-slate-400">Block steep slope paths & swollen riverbanks</div>
            </div>
            <input
              type="checkbox"
              checked={showMonsoonDisruptions}
              onChange={(e) => setShowMonsoonDisruptions(e.target.checked)}
              className="w-4 h-4 accent-emerald-500 rounded cursor-pointer"
            />
          </label>
        </div>

        {/* Legend */}
        <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800/80 space-y-2">
          <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
            <Layers className="w-3.5 h-3.5 text-emerald-400" />
            <span>{t.legendTitle}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50"></span>
              <span className="text-slate-300">{t.legendUnder30}</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 rounded-full bg-yellow-400 shadow-sm shadow-yellow-400/50"></span>
              <span className="text-slate-300">{t.legend30to60}</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 rounded-full bg-orange-500 shadow-sm shadow-orange-500/50"></span>
              <span className="text-slate-300">{t.legend60to90}</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-3 h-3 rounded-full bg-red-500 shadow-sm shadow-red-500/50"></span>
              <span className="text-slate-300">{t.legendOver90}</span>
            </div>
          </div>
          <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-3 border-2 border-blue-400 bg-blue-600 rounded"></span>
              <span>Health Facility</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="text-amber-400 text-sm">★</span>
              <span>Recommended Site</span>
            </span>
          </div>
        </div>

        {/* Scientific disclaimer notice */}
        <div className="p-3 bg-amber-950/30 border border-amber-800/40 rounded-lg flex items-start space-x-2 text-[11px] text-amber-300/90 leading-relaxed">
          <Info className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-400" />
          <span>{t.disclaimer}</span>
        </div>
      </div>

      {/* Main Interactive Map Canvas */}
      <div className="flex-1 relative bg-slate-950 flex items-center justify-center overflow-hidden">
        {/* Map Header Status Banner */}
        <div className="absolute top-4 left-6 z-10 bg-slate-900/90 backdrop-blur-md px-4 py-2 rounded-xl border border-slate-800 shadow-xl flex items-center space-x-4 text-xs">
          <div>
            <span className="text-slate-400">Total Habitations:</span>{' '}
            <span className="font-bold text-white">{habitations.length}</span>
          </div>
          <div className="h-4 w-px bg-slate-700"></div>
          <div>
            <span className="text-slate-400">Underserved (&gt;{thresholdMin}m):</span>{' '}
            <span className="font-bold text-red-400">
              {habitations.filter((h) => (travelMode === 'walk' ? h.travel_time_min.base : h.hybrid_time_min) > thresholdMin).length}
            </span>
          </div>
          <div className="h-4 w-px bg-slate-700"></div>
          <div>
            <span className="text-slate-400">Candidate Sites:</span>{' '}
            <span className="font-bold text-amber-400">{candidates.length}</span>
          </div>
        </div>

        {/* SVG Terrain Map */}
        <svg
          viewBox={`0 0 ${mapWidth} ${mapHeight}`}
          className="w-full h-full max-h-[85vh] select-none cursor-crosshair"
        >
          <defs>
            {/* Mountain terrain background pattern */}
            <radialGradient id="mountainGlow" cx="50%" cy="50%" r="60%">
              <stop offset="0%" stopColor="#1e293b" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#090d16" stopOpacity="1" />
            </radialGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="2.5" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background Map Frame */}
          <rect width={mapWidth} height={mapHeight} fill="url(#mountainGlow)" />

          {/* Synthetic Elevation Contours / Valley Shading */}
          {showContours && (
            <g opacity="0.35">
              <path
                d="M 60,180 Q 250,120 400,220 T 740,280"
                fill="none"
                stroke="#334155"
                strokeWidth="1.5"
                strokeDasharray="4 4"
              />
              <path
                d="M 80,320 Q 300,260 520,380 T 760,420"
                fill="none"
                stroke="#334155"
                strokeWidth="1.5"
                strokeDasharray="4 4"
              />
              <path
                d="M 120,80 Q 380,180 500,100 T 700,140"
                fill="none"
                stroke="#334155"
                strokeWidth="1.2"
                strokeDasharray="4 4"
              />
            </g>
          )}

          {/* Main River Gorge */}
          <path
            d="M 220,40 Q 290,200 400,280 T 580,520"
            fill="none"
            stroke="#0284c7"
            strokeWidth={showMonsoonDisruptions ? '6' : '3.5'}
            strokeLinecap="round"
            opacity={showMonsoonDisruptions ? '0.85' : '0.6'}
          />
          {/* River Bridge */}
          <line x1="390" y1="275" x2="410" y2="285" stroke="#f8fafc" strokeWidth="4" strokeLinecap="square" />

          {/* Motorable Hill Highway */}
          <path
            d="M 60,340 Q 240,290 400,280 T 740,210"
            fill="none"
            stroke="#64748b"
            strokeWidth="3.5"
            strokeDasharray="6 3"
            opacity="0.7"
          />

          {/* Monsoon Landslide Disruption Scars (v1.1 SAR) */}
          {showMonsoonDisruptions && (
            <g opacity="0.9">
              <circle cx="340" cy="245" r="14" fill="#dc2626" opacity="0.4" />
              <circle cx="340" cy="245" r="6" fill="#ef4444" />
              <text x="358" y="248" fill="#fca5a5" fontSize="10" fontWeight="bold">
                ⚠️ SAR Landslide Scar
              </text>

              <circle cx="510" cy="390" r="16" fill="#0284c7" opacity="0.4" />
              <text x="532" y="394" fill="#7dd3fc" fontSize="10" fontWeight="bold">
                🌊 Flash Flood Inundation
              </text>
            </g>
          )}

          {/* Habitations (Villages & Hamlets) */}
          {habitations.map((hab) => {
            const [cx, cy] = project(hab.lat, hab.lon);
            const timeVal = travelMode === 'walk' ? hab.travel_time_min.base : hab.hybrid_time_min;
            const color = getTravelTimeColor(timeVal);
            const isHovered = hoveredHab?.id === hab.id;
            const r = Math.max(3.5, Math.min(8.0, Math.sqrt(hab.population) / 3.0));

            return (
              <g
                key={hab.id}
                className="cursor-pointer transition-transform duration-150"
                onClick={() => onSelectHabitation(hab)}
                onMouseEnter={() => setHoveredHab(hab)}
                onMouseLeave={() => setHoveredHab(null)}
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? r + 3 : r}
                  fill={color}
                  stroke={isHovered ? '#ffffff' : '#0f172a'}
                  strokeWidth={isHovered ? 2.5 : 1.2}
                  opacity={timeVal > thresholdMin ? 0.95 : 0.8}
                  filter={timeVal > thresholdMin ? 'url(#glow)' : undefined}
                />
              </g>
            );
          })}

          {/* Health Facilities */}
          {filteredFacilities.map((fac) => {
            const [cx, cy] = project(fac.lat, fac.lon);
            return (
              <g key={fac.id} className="cursor-pointer">
                {/* Outer hospital marker square */}
                <rect
                  x={cx - 7}
                  y={cy - 7}
                  width="14"
                  height="14"
                  rx="3"
                  fill="#0284c7"
                  stroke="#ffffff"
                  strokeWidth="1.8"
                  className="shadow-lg"
                />
                {/* White cross inside */}
                <line x1={cx} y1={cy - 4} x2={cx} y2={cy + 4} stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
                <line x1={cx - 4} y1={cy} x2={cx + 4} y2={cy} stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
                {/* Facility name label */}
                <text
                  x={cx + 10}
                  y={cy + 4}
                  fill="#ffffff"
                  fontSize="10"
                  fontWeight="600"
                  className="pointer-events-none drop-shadow-md"
                >
                  {fac.name}
                </text>
              </g>
            );
          })}

          {/* Recommended Candidate Sites (Optimizer Top Recommendations) */}
          {candidates.map((cand) => {
            const [cx, cy] = project(cand.lat, cand.lon);
            return (
              <g
                key={cand.id}
                className="cursor-pointer group"
                onClick={() => onSelectCandidate(cand)}
              >
                {/* Pulsing ring */}
                <circle cx={cx} cy={cy} r="18" fill="#f59e0b" opacity="0.25" className="animate-ping" />
                {/* Star marker */}
                <circle cx={cx} cy={cy} r="10" fill="#f59e0b" stroke="#ffffff" strokeWidth="2" />
                <text
                  x={cx}
                  y={cy + 3.5}
                  textAnchor="middle"
                  fill="#1e293b"
                  fontSize="10"
                  fontWeight="900"
                  className="pointer-events-none"
                >
                  ★
                </text>
                {/* Badge showing newly covered population */}
                <rect
                  x={cx - 32}
                  y={cy - 24}
                  width="64"
                  height="16"
                  rx="4"
                  fill="#1e293b"
                  stroke="#f59e0b"
                  strokeWidth="1"
                />
                <text
                  x={cx}
                  y={cy - 12}
                  textAnchor="middle"
                  fill="#fbbf24"
                  fontSize="9"
                  fontWeight="bold"
                >
                  +{cand.gain_pop} pop
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Popup */}
        {hoveredHab && (
          <div className="absolute bottom-6 right-6 bg-slate-900/95 backdrop-blur-md p-4 rounded-xl border border-slate-700 shadow-2xl max-w-sm pointer-events-none animate-in fade-in zoom-in-95 duration-100 z-20">
            <div className="flex items-center justify-between space-x-2">
              <span className="font-bold text-white text-sm">{hoveredHab.name}</span>
              <span className="text-[10px] text-slate-400">{hoveredHab.block}</span>
            </div>
            <div className="mt-2 space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Walking Time (Base):</span>
                <span
                  className="font-bold"
                  style={{ color: getTravelTimeColor(hoveredHab.travel_time_min.base) }}
                >
                  {hoveredHab.travel_time_min.base} min
                </span>
              </div>
              <div className="flex justify-between text-slate-400 text-[11px]">
                <span>Uncertainty Range:</span>
                <span className="text-slate-200">
                  {hoveredHab.travel_time_min.low}m - {hoveredHab.travel_time_min.high}m
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Population:</span>
                <span className="text-white font-medium">{hoveredHab.population.toLocaleString()}</span>
              </div>
              {hoveredHab.nearest_facility && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Nearest Center:</span>
                  <span className="text-emerald-400 font-medium">{hoveredHab.nearest_facility.name}</span>
                </div>
              )}
            </div>
            <p className="mt-2 text-[10px] text-slate-400 border-t border-slate-800 pt-1.5">
              Click village node to open full accessibility profile.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
