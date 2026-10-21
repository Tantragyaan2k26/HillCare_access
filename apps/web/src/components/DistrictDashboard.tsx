import React, { useMemo } from 'react';
import {
  Users,
  Clock,
  AlertTriangle,
  Building2,
  TrendingDown,
  BarChart,
  CheckCircle,
  HelpCircle,
} from 'lucide-react';
import { HabitationItem, RegionSummary } from '../types';
import { TranslationDict } from '../i18n/translations';

interface DistrictDashboardProps {
  summary: RegionSummary | null;
  habitations: HabitationItem[];
  t: TranslationDict;
}

export const DistrictDashboard: React.FC<DistrictDashboardProps> = ({ summary, habitations, t }) => {
  if (!summary) {
    return (
      <div className="flex items-center justify-center h-96 text-slate-400 text-sm">
        Loading district accessibility analytics...
      </div>
    );
  }

  // Aggregate stats per block
  const blockStats = useMemo(() => {
    const blocks: Record<string, { totalPop: number; habCount: number; underservedPop: number; times: number[] }> = {};
    for (const h of habitations) {
      const bname = h.block || 'General Block';
      if (!blocks[bname]) {
        blocks[bname] = { totalPop: 0, habCount: 0, underservedPop: 0, times: [] };
      }
      blocks[bname].totalPop += h.population;
      blocks[bname].habCount += 1;
      blocks[bname].times.push(h.travel_time_min.base);
      if (h.travel_time_min.base > 60) {
        blocks[bname].underservedPop += h.population;
      }
    }

    return Object.entries(blocks)
      .map(([name, data]) => {
        const avgTime = data.times.length ? data.times.reduce((a, b) => a + b, 0) / data.times.length : 0;
        const undPct = data.totalPop > 0 ? (data.underservedPop / data.totalPop) * 100 : 0;
        return {
          name,
          totalPop: data.totalPop,
          habCount: data.habCount,
          underservedPop: data.underservedPop,
          underservedPct: Math.round(undPct * 10) / 10,
          meanTimeMin: Math.round(avgTime),
        };
      })
      .sort((a, b) => b.underservedPct - a.underservedPct);
  }, [habitations]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title */}
      <div>
        <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-1">
          <BarChart className="w-4 h-4" />
          <span>Regional Health Access Profile</span>
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">
          {summary.region_name} District Dashboard
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Aggregated accessibility indicators across all habitations, blocks, and terrain sectors.
        </p>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Population */}
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl shadow-lg space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>{t.kpiTotalPop}</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">
            {summary.total_population.toLocaleString()}
          </div>
          <div className="text-xs text-slate-400">
            Across {summary.total_habitations} surveyed habitations & hamlets
          </div>
        </div>

        {/* Underserved Population @ 60m */}
        <div className="bg-slate-900 border border-red-950/80 p-5 rounded-2xl shadow-lg space-y-2 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-24 h-24 bg-red-600/10 rounded-full blur-2xl"></div>
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>{t.kpiUnderservedPop} (60m)</span>
            <AlertTriangle className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-3xl font-extrabold text-red-400">
            {summary.underserved_pct_60min}%
          </div>
          <div className="text-xs text-slate-400">
            Cannot reach a functional PHC within 1 hour on foot
          </div>
        </div>

        {/* Mean Walking Time */}
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl shadow-lg space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>{t.kpiMeanTime}</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-extrabold text-amber-400">
            {summary.mean_travel_time_min} min
          </div>
          <div className="text-xs text-slate-400">
            Median walking time: {summary.median_travel_time_min} min
          </div>
        </div>

        {/* Functional Facilities */}
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl shadow-lg space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>{t.kpiFacilities}</span>
            <Building2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-extrabold text-emerald-400">
            {summary.functional_facilities_count}
          </div>
          <div className="text-xs text-slate-400">
            Operating DH, CHC, and functional PHC units
          </div>
        </div>
      </div>

      {/* Threshold Sensitivity Analysis (30, 60, 90 mins) */}
      <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Threshold Sensitivity Analysis</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Comparison across standard planning thresholds. No single threshold should dictate access policy alone.
            </p>
          </div>
          <span className="px-3 py-1 bg-slate-800 text-slate-300 rounded-lg text-xs font-medium">
            Tobler Baseline Model
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* 30 Minutes */}
          <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-3">
            <div className="flex justify-between items-center text-xs font-semibold text-slate-300">
              <span>30 Minutes Target</span>
              <span className="text-emerald-400">HWC Standard</span>
            </div>
            <div className="text-2xl font-black text-white">{summary.underserved_pct_30min}%</div>
            <div className="w-full bg-slate-700 h-2 rounded-full overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full"
                style={{ width: `${Math.min(100, summary.underserved_pct_30min)}%` }}
              ></div>
            </div>
            <p className="text-[11px] text-slate-400 leading-normal">
              Habitations beyond 30 min walking time from basic health posts.
            </p>
          </div>

          {/* 60 Minutes */}
          <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-3">
            <div className="flex justify-between items-center text-xs font-semibold text-slate-300">
              <span>60 Minutes Target</span>
              <span className="text-amber-400">Primary Care (PHC)</span>
            </div>
            <div className="text-2xl font-black text-amber-400">{summary.underserved_pct_60min}%</div>
            <div className="w-full bg-slate-700 h-2 rounded-full overflow-hidden">
              <div
                className="bg-amber-400 h-full rounded-full"
                style={{ width: `${Math.min(100, summary.underserved_pct_60min)}%` }}
              ></div>
            </div>
            <p className="text-[11px] text-slate-400 leading-normal">
              Habitations exceeding 1 hour walking time to a functional doctor post.
            </p>
          </div>

          {/* 90 Minutes */}
          <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-3">
            <div className="flex justify-between items-center text-xs font-semibold text-slate-300">
              <span>90 Minutes Target</span>
              <span className="text-red-400">Critical Isolation</span>
            </div>
            <div className="text-2xl font-black text-red-400">{summary.underserved_pct_90min}%</div>
            <div className="w-full bg-slate-700 h-2 rounded-full overflow-hidden">
              <div
                className="bg-red-500 h-full rounded-full"
                style={{ width: `${Math.min(100, summary.underserved_pct_90min)}%` }}
              ></div>
            </div>
            <p className="text-[11px] text-slate-400 leading-normal">
              Severely isolated villages requiring urgent outreach or sub-centres.
            </p>
          </div>
        </div>
      </div>

      {/* Block Breakdown & Priority Ranking Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Block-Level Vulnerability Ranking</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Ranked by proportion of population exceeding the 60-minute travel threshold.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Block Name</th>
                <th className="py-3 px-4">Population</th>
                <th className="py-3 px-4">Habitations</th>
                <th className="py-3 px-4">Mean Walk Time</th>
                <th className="py-3 px-4">Underserved Pop</th>
                <th className="py-3 px-4">% Underserved</th>
                <th className="py-3 px-4">Priority Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
              {blockStats.map((b, idx) => (
                <tr key={b.name} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-3.5 px-4 font-bold text-white flex items-center space-x-2">
                    <span className="w-5 h-5 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center text-[10px]">
                      {idx + 1}
                    </span>
                    <span>{b.name}</span>
                  </td>
                  <td className="py-3.5 px-4 font-medium">{b.totalPop.toLocaleString()}</td>
                  <td className="py-3.5 px-4">{b.habCount} villages</td>
                  <td className="py-3.5 px-4 font-mono text-amber-300">{b.meanTimeMin} min</td>
                  <td className="py-3.5 px-4">{b.underservedPop.toLocaleString()}</td>
                  <td className="py-3.5 px-4 font-bold">
                    <span className={b.underservedPct > 50 ? 'text-red-400' : 'text-amber-400'}>
                      {b.underservedPct}%
                    </span>
                  </td>
                  <td className="py-3.5 px-4">
                    {b.underservedPct > 60 ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-950 text-red-400 border border-red-800">
                        CRITICAL PRIORITY
                      </span>
                    ) : b.underservedPct > 35 ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-950 text-amber-400 border border-amber-800">
                        MODERATE PRIORITY
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                        FAIR ACCESS
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
