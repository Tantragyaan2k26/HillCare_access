import React from 'react';
import { BookOpen, Mountain, ArrowRight, ShieldAlert, Cpu, Sparkles, Layers } from 'lucide-react';
import { TranslationDict } from '../i18n/translations';

interface MethodologyViewProps {
  t: TranslationDict;
}

export const MethodologyView: React.FC<MethodologyViewProps> = ({ t }) => {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10 text-slate-200">
      {/* Title */}
      <div>
        <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-1">
          <BookOpen className="w-4 h-4" />
          <span>Scientific Core & Engineering Principles</span>
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">Methodology & Mathematical Formulation</h1>
        <p className="text-sm text-slate-400 mt-2 leading-relaxed">
          How HillCare Access models realistic mountain travel time and recommends health facility locations.
        </p>
      </div>

      {/* 1. Tobler's Hiking Function */}
      <section className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl space-y-4">
        <div className="flex items-center space-x-2.5 text-emerald-400 font-bold text-lg">
          <Mountain className="w-5 h-5" />
          <h2>1. Tobler's Hiking Function (1993)</h2>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          Straight-line Euclidean distance in the Himalayas is misleading: a village 3 km away across a 1,000-meter gorge
          takes hours of steep ascent, whereas a village 3 km along a gentle valley floor is easily reachable.
        </p>
        <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 font-mono text-center text-sm text-emerald-400">
          v(S) = 6.0 · exp(-3.5 · |S + 0.05|) [km/h]
        </div>
        <ul className="text-xs text-slate-400 space-y-2 list-disc list-inside">
          <li>
            <strong className="text-slate-200">Slope S:</strong> Signed rise over run (Δz / Δx) along the direction of travel.
          </li>
          <li>
            <strong className="text-slate-200">Peak Speed:</strong> 5.037 km/h at a gentle downhill (S = -0.05, ~5% grade).
          </li>
          <li>
            <strong className="text-slate-200">Asymmetry:</strong> Walking uphill from valley to ridge takes far longer than
            descending from ridge to valley.
          </li>
          <li>
            <strong className="text-slate-200">Carried Patient Mode:</strong> In emergency evacuation or stretcher carriage,
            walking time is multiplied by 2.0x (configurable).
          </li>
        </ul>
      </section>

      {/* 2. 16-Neighbour Connectivity & Graph Inversion */}
      <section className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl space-y-4">
        <div className="flex items-center space-x-2.5 text-emerald-400 font-bold text-lg">
          <Layers className="w-5 h-5" />
          <h2>2. 16-Neighbour Connectivity & Reverse Graph Dijkstra</h2>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          Standard 4- or 8-neighbour grid graphs suffer from severe directional bias (diagonal paths appear ~41% longer than
          Euclidean straight lines). HillCare constructs a 16-neighbour connectivity graph (8 Queen moves + 8 Knight moves)
          over Digital Elevation Models (Copernicus GLO-30 / ALOS), which reduces metric distortion to under 2.5%.
        </p>
        <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800 text-xs space-y-2">
          <div className="font-bold text-white flex items-center space-x-2">
            <span>Graph Inversion Theorem:</span>
          </div>
          <p className="text-slate-400">
            Patients travel from <span className="text-amber-400 font-semibold">Habitation → Health Facility</span>. Running
            Dijkstra from each habitation individually would require thousands of searches. Instead, HillCare inverts every
            edge's slope sign in the cost graph (S_rev = -S_fwd) and runs a single multi-source Dijkstra pass outward from all
            functional health facilities. The accumulated values at each raster cell represent exact Habitation → Facility
            walking times.
          </p>
        </div>
      </section>

      {/* 3. Earth Observation (v1.1) */}
      <section className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl space-y-4">
        <div className="flex items-center space-x-2.5 text-blue-400 font-bold text-lg">
          <Cpu className="w-5 h-5" />
          <h2>3. Satellite Earth Observation & Seasonal SAR (v1.1)</h2>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          During the Indian monsoon (June–September), dense cloud cover blinds conventional optical satellites. HillCare
          integrates Sentinel-1 C-band Synthetic Aperture Radar (SAR), which penetrates clouds and rain to detect:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
            <div className="font-bold text-white mb-1">Monsoon Landslide Scars</div>
            <p className="text-slate-400">
              Backscatter change (&lt; -4.5 dB) on slopes &gt; 25° indicates slope failure, turning trails into impassable barriers.
            </p>
          </div>
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
            <div className="font-bold text-white mb-1">Specular Water Masking</div>
            <p className="text-slate-400">
              Low SAR backscatter (&lt; -18 dB) detects river swelling and bridge submersion in mountain gorges.
            </p>
          </div>
        </div>
      </section>

      {/* 4. Limitations and Non-Claims */}
      <section className="bg-amber-950/20 border border-amber-800/40 p-6 rounded-2xl space-y-3">
        <div className="flex items-center space-x-2 text-amber-400 font-bold text-base">
          <ShieldAlert className="w-5 h-5" />
          <h3>Scientific Limitations & Boundary of Claims</h3>
        </div>
        <ul className="text-xs text-amber-200/90 space-y-2 list-disc list-inside leading-relaxed">
          <li>
            <strong>Geographic Access Only:</strong> HillCare Access measures physical walking accessibility on terrain. It does
            not measure healthcare utilization, clinical quality, doctor absenteeism, or unmet clinical disease burden.
          </li>
          <li>
            <strong>DEM Smoothing:</strong> 30m rasters smooth micro-terrain cliffs and staircases. HillCare reports calibrated
            uncertainty ranges (low 0.8x, base 1.0x, high 1.2x).
          </li>
          <li>
            <strong>Field Verification:</strong> All candidate siting recommendations should be ground-truthed by district health
            officers and local panchayats before capital expenditure.
          </li>
        </ul>
      </section>
    </div>
  );
};
