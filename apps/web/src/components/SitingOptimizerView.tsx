import React, { useState } from 'react';
import {
  Target,
  Users,
  Award,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  TrendingDown,
  Building,
  CheckCircle2,
} from 'lucide-react';
import { CandidateItem, Objective, RegionSummary } from '../types';
import { TranslationDict } from '../i18n/translations';

interface SitingOptimizerViewProps {
  candidates: CandidateItem[];
  summary: RegionSummary | null;
  t: TranslationDict;
  selectedDistrictName: string;
  onSelectCandidate: (cand: CandidateItem) => void;
}

export const SitingOptimizerView: React.FC<SitingOptimizerViewProps> = ({
  candidates,
  summary,
  t,
  selectedDistrictName,
  onSelectCandidate,
}) => {
  const [activeObjective, setActiveObjective] = useState<Objective>('max_new_coverage');

  const totalPop = summary?.total_population || 1;
  const topCandidate = candidates.length > 0 ? candidates[0] : null;

  // Impact projection
  const currentUnderserved = Math.round((summary?.underserved_pct_60min || 0) * (totalPop / 100));
  const newlyCovered = topCandidate?.gain_pop || 0;
  const projectedUnderserved = Math.max(0, currentUnderserved - newlyCovered);
  const projectedPct = Math.round((projectedUnderserved / totalPop) * 1000) / 10;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-1">
            <Target className="w-4 h-4" />
            <span>Optimal Health Facility Siting (Greedy Submodular Maximization)</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            {selectedDistrictName} Facility Siting Optimizer
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Recommends exact geographic coordinates for new health facilities that maximize newly covered population.
          </p>
        </div>

        {/* Objective Selector Buttons */}
        <div className="flex bg-slate-900 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveObjective('max_new_coverage')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeObjective === 'max_new_coverage'
                ? 'bg-emerald-600 text-white shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Max Population
          </button>
          <button
            onClick={() => setActiveObjective('equity_weighted')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeObjective === 'equity_weighted'
                ? 'bg-emerald-600 text-white shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Equity Weighted
          </button>
          <button
            onClick={() => setActiveObjective('min_mean_time')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeObjective === 'min_mean_time'
                ? 'bg-emerald-600 text-white shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Min Mean Time
          </button>
        </div>
      </div>

      {/* Before & After Impact Projection Card */}
      {topCandidate && (
        <div className="bg-gradient-to-r from-emerald-950/60 via-slate-900 to-slate-900 border border-emerald-800/60 p-6 rounded-2xl shadow-2xl relative overflow-hidden">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <span className="px-2.5 py-0.5 bg-emerald-500 text-slate-950 font-black text-xs rounded-full">
                  RANK #1 RECOMMENDATION
                </span>
                <span className="text-xs text-emerald-400 font-semibold">
                  Lat: {topCandidate.lat}, Lon: {topCandidate.lon}
                </span>
              </div>
              <h2 className="text-2xl font-bold text-white">
                Placing 1 New Facility Newly Covers{' '}
                <span className="text-emerald-400 font-black">+{topCandidate.gain_pop.toLocaleString()}</span> People
              </h2>
              <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
                By placing a new Primary Health Centre at this feasible site, {topCandidate.gain_pop.toLocaleString()} currently
                isolated citizens will be brought within the 60-minute walking radius to care.
              </p>
            </div>

            {/* Before vs After Numbers */}
            <div className="flex items-center space-x-4 bg-slate-950/80 p-4 rounded-xl border border-slate-800 flex-shrink-0">
              <div className="text-center px-3">
                <div className="text-[10px] text-slate-400 uppercase font-bold">Current Underserved</div>
                <div className="text-xl font-bold text-red-400 mt-1">{summary?.underserved_pct_60min}%</div>
                <div className="text-[10px] text-slate-400">{currentUnderserved.toLocaleString()} pop</div>
              </div>

              <ArrowRight className="w-5 h-5 text-emerald-400" />

              <div className="text-center px-3">
                <div className="text-[10px] text-slate-400 uppercase font-bold">With New Facility</div>
                <div className="text-xl font-extrabold text-emerald-400 mt-1">{projectedPct}%</div>
                <div className="text-[10px] text-emerald-300 font-medium">{projectedUnderserved.toLocaleString()} pop</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Ranked Candidate Sites List */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Top Feasible Candidate Locations</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Filtered for terrain feasibility (slope &lt; 25°), outside river gorges, and ranked by submodular gain.
            </p>
          </div>
          <span className="text-xs text-emerald-400 font-semibold bg-emerald-950 px-3 py-1 rounded-lg border border-emerald-800">
            (1 - 1/e) Approximation Guarantee
          </span>
        </div>

        <div className="divide-y divide-slate-800/80">
          {candidates.map((cand) => (
            <div
              key={cand.id}
              onClick={() => onSelectCandidate(cand)}
              className="p-5 hover:bg-slate-800/40 transition-colors cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="flex items-start space-x-4">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center flex-shrink-0 text-amber-400 font-extrabold text-lg">
                  #{cand.rank}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-white text-base">Candidate Site #{cand.id}</span>
                    <span className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">
                      {cand.lat.toFixed(4)}°N, {cand.lon.toFixed(4)}°E
                    </span>
                    <span className="px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded text-[10px] flex items-center space-x-1">
                      <ShieldCheck className="w-3 h-3" />
                      <span>Terrain Feasible</span>
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1 flex items-center space-x-4">
                    <span>Mean Time Savings: <strong className="text-slate-200">-{cand.mean_time_delta} min</strong></span>
                    <span>•</span>
                    <span>Equity Score: <strong className="text-purple-300">{cand.equity_score}</strong></span>
                  </div>
                </div>
              </div>

              {/* Pop Gain Badge */}
              <div className="flex items-center space-x-3 self-end md:self-center">
                <div className="text-right">
                  <div className="text-2xl font-black text-amber-400">+{cand.gain_pop.toLocaleString()}</div>
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Newly Covered Population</div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectCandidate(cand);
                  }}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-colors"
                >
                  Inspect on Map
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
