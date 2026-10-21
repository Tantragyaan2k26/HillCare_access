import React, { useState } from 'react';
import {
  Compass,
  Play,
  CheckCircle2,
  AlertCircle,
  FileDown,
  RotateCcw,
  Sparkles,
  Loader2,
} from 'lucide-react';
import { ScenarioResponse } from '../types';
import { createScenario } from '../services/api';
import { TranslationDict } from '../i18n/translations';

interface ScenarioWorkspaceProps {
  districtId: number;
  selectedDistrictName: string;
  t: TranslationDict;
}

export const ScenarioWorkspace: React.FC<ScenarioWorkspaceProps> = ({
  districtId,
  selectedDistrictName,
  t,
}) => {
  const [scenarioName, setScenarioName] = useState(`New PHC Siting Scenario - ${selectedDistrictName}`);
  const [tier, setTier] = useState('PHC');
  const [thresholdMin, setThresholdMin] = useState(60);
  const [travelMode, setTravelMode] = useState('hybrid');
  const [objective, setObjective] = useState('max_new_coverage');
  const [kFacilities, setKFacilities] = useState(1);
  const [loading, setLoading] = useState(false);
  const [scenarioResult, setScenarioResult] = useState<ScenarioResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmitScenario = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await createScenario({
        name: scenarioName,
        region_id: districtId,
        tier,
        threshold_min: thresholdMin,
        mode: travelMode,
        objective,
        k: kFacilities,
        calibration: 1.0,
      });
      setScenarioResult(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to execute scenario');
    } finally {
      setLoading(false);
    }
  };

  const exportReport = () => {
    if (!scenarioResult) return;
    const jsonStr = JSON.stringify(scenarioResult, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${scenarioResult.id}_report.json`;
    a.click();
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title */}
      <div>
        <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-1">
          <Compass className="w-4 h-4" />
          <span>Interactive Planner Workspace</span>
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">
          What-If Scenario Simulation
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Model the geographic accessibility impact of opening hypothetical health facilities or adjusting norms.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Scenario Parameters Form */}
        <form
          onSubmit={handleSubmitScenario}
          className="lg:col-span-2 bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl space-y-5"
        >
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Scenario Name</label>
            <input
              type="text"
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              required
              className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Target Facility Tier</label>
              <select
                value={tier}
                onChange={(e) => setTier(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm text-white focus:ring-emerald-500"
              >
                <option value="PHC">Primary Health Centre (PHC)</option>
                <option value="HWC">Health & Wellness Centre (HWC)</option>
                <option value="CHC">Community Health Centre (CHC)</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Walking Threshold</label>
              <select
                value={thresholdMin}
                onChange={(e) => setThresholdMin(Number(e.target.value))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm text-white focus:ring-emerald-500"
              >
                <option value={30}>30 minutes (HWC Target)</option>
                <option value={45}>45 minutes</option>
                <option value={60}>60 minutes (Standard PHC Norm)</option>
                <option value={90}>90 minutes (Maximum Remote)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Travel Mode</label>
              <select
                value={travelMode}
                onChange={(e) => setTravelMode(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm text-white focus:ring-emerald-500"
              >
                <option value="hybrid">Hybrid (Walk to road + Vehicle)</option>
                <option value="walk">Pure Terrain Walking</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Facilities to Place (k)</label>
              <select
                value={kFacilities}
                onChange={(e) => setKFacilities(Number(e.target.value))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm text-white focus:ring-emerald-500"
              >
                <option value={1}>1 New Facility</option>
                <option value={2}>2 New Facilities</option>
                <option value={3}>3 New Facilities</option>
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Optimization Objective</label>
            <select
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm text-white focus:ring-emerald-500"
            >
              <option value="max_new_coverage">Max Newly Covered Underserved Population</option>
              <option value="equity_weighted">Equity-Weighted (SC/ST representation)</option>
              <option value="min_mean_time">Minimize Population-Weighted Mean Travel Time</option>
            </select>
          </div>

          {errorMsg && (
            <div className="p-3 bg-red-950/60 border border-red-800 text-red-300 text-xs rounded-lg flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="pt-2 flex justify-end space-x-3">
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white font-semibold text-sm rounded-xl flex items-center space-x-2 transition-all shadow-lg shadow-emerald-900/30"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Computing Dijkstra Surfaces...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>Run Scenario Simulation</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Live Scenario Result Summary */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-white">Scenario Status</h2>
              {scenarioResult ? (
                <span className="px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 text-xs font-bold rounded-md flex items-center space-x-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>SUCCEEDED</span>
                </span>
              ) : (
                <span className="text-xs text-slate-500">Ready to run</span>
              )}
            </div>

            {scenarioResult?.result ? (
              <div className="space-y-3 pt-2 text-xs">
                <div className="p-3 bg-slate-800/60 rounded-xl space-y-1">
                  <div className="text-slate-400">Newly Covered Population</div>
                  <div className="text-2xl font-black text-emerald-400">
                    +{scenarioResult.result.total_newly_covered_population.toLocaleString()} pop
                  </div>
                </div>

                <div className="p-3 bg-slate-800/60 rounded-xl space-y-1">
                  <div className="text-slate-400">Recommended Sites Selected</div>
                  <div className="text-lg font-bold text-white">
                    {scenarioResult.result.top_candidates_selected} Optimal Locations
                  </div>
                </div>

                <div className="p-3 bg-slate-800/60 rounded-xl space-y-1">
                  <div className="text-slate-400">Run Identifier</div>
                  <div className="font-mono text-slate-300 text-[11px] truncate">{scenarioResult.run_id}</div>
                </div>
              </div>
            ) : (
              <div className="p-6 text-center text-slate-500 text-xs border border-dashed border-slate-800 rounded-xl">
                Configure your parameters on the left and click "Run Scenario Simulation" to evaluate the impact.
              </div>
            )}
          </div>

          {scenarioResult && (
            <div className="pt-4 border-t border-slate-800">
              <button
                onClick={exportReport}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg flex items-center justify-center space-x-2 transition-colors"
              >
                <FileDown className="w-4 h-4 text-emerald-400" />
                <span>Export Scenario JSON Report</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
