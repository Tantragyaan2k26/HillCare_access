import React from 'react';
import { X, Clock, MapPin, Users, ShieldAlert, Award, Footprints, Car, AlertCircle } from 'lucide-react';
import { HabitationItem } from '../types';
import { TranslationDict } from '../i18n/translations';

interface VillageDetailModalProps {
  habitation: HabitationItem | null;
  onClose: () => void;
  t: TranslationDict;
}

export const VillageDetailModal: React.FC<VillageDetailModalProps> = ({ habitation, onClose, t }) => {
  if (!habitation) return null;

  const formatHoursMins = (minutes: number) => {
    const hrs = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    if (hrs === 0) return `${mins} min`;
    return `${hrs}h ${mins}m`;
  };

  const getStatusColor = (min: number) => {
    if (min <= 30) return 'text-emerald-400 bg-emerald-950/60 border-emerald-800';
    if (min <= 60) return 'text-amber-400 bg-amber-950/60 border-amber-800';
    if (min <= 90) return 'text-orange-400 bg-orange-950/60 border-orange-800';
    return 'text-red-400 bg-red-950/60 border-red-800';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-start justify-between bg-slate-950/50">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-md">
                Habitation ID #{habitation.id}
              </span>
              <span className="text-xs text-slate-400">Block: {habitation.block}</span>
            </div>
            <h2 className="text-xl font-bold text-white mt-1">{habitation.name}</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          {/* Main Travel Time Metric */}
          <div className="p-4 rounded-xl bg-slate-800/80 border border-slate-700/80 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                <Clock className="w-4 h-4 text-emerald-400" />
                <span>Modelled Walking Time</span>
              </span>
              <div className="text-3xl font-extrabold text-white">
                {formatHoursMins(habitation.travel_time_min.base)}
              </div>
              <div className="text-xs text-slate-400">
                Range: {formatHoursMins(habitation.travel_time_min.low)} (fast pace) to{' '}
                {formatHoursMins(habitation.travel_time_min.high)} (difficult terrain)
              </div>
            </div>

            <div className={`px-3 py-1.5 rounded-lg border text-xs font-bold ${getStatusColor(habitation.travel_time_min.base)}`}>
              {habitation.travel_time_min.base > 60 ? 'UNDERSERVED' : 'SERVED'}
            </div>
          </div>

          {/* Travel Modes Comparison */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-slate-800/50 border border-slate-700/60 rounded-xl">
              <div className="flex items-center space-x-2 text-xs text-slate-400 mb-1">
                <Footprints className="w-4 h-4 text-emerald-400" />
                <span>Pure Walking</span>
              </div>
              <div className="text-lg font-bold text-white">{Math.round(habitation.travel_time_min.base)} min</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Measures physical isolation</div>
            </div>

            <div className="p-3 bg-slate-800/50 border border-slate-700/60 rounded-xl">
              <div className="flex items-center space-x-2 text-xs text-slate-400 mb-1">
                <Car className="w-4 h-4 text-blue-400" />
                <span>Hybrid (Walk + Road)</span>
              </div>
              <div className="text-lg font-bold text-white">{Math.round(habitation.hybrid_time_min)} min</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Walk to road + 20m wait + vehicle</div>
            </div>
          </div>

          {/* Nearest Health Facility */}
          {habitation.nearest_facility && (
            <div className="p-4 bg-slate-800/40 border border-slate-700/60 rounded-xl space-y-2">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <MapPin className="w-4 h-4 text-emerald-400" />
                <span>Nearest Functional Health Facility</span>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-base font-bold text-white">{habitation.nearest_facility.name}</div>
                  <div className="text-xs text-emerald-400 font-medium">Tier: {habitation.nearest_facility.tier}</div>
                </div>
                <span className="px-2.5 py-1 text-xs bg-emerald-950 text-emerald-300 border border-emerald-800 rounded-md font-medium">
                  Functional
                </span>
              </div>
            </div>
          )}

          {/* Demographics */}
          <div className="p-4 bg-slate-800/40 border border-slate-700/60 rounded-xl space-y-3">
            <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <Users className="w-4 h-4 text-blue-400" />
              <span>Census Demographics</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-400">Population</div>
                <div className="text-sm font-bold text-white">{habitation.population.toLocaleString()}</div>
              </div>
              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-400">SC Share</div>
                <div className="text-sm font-bold text-purple-400">{habitation.sc_pct}%</div>
              </div>
              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-400">ST Share</div>
                <div className="text-sm font-bold text-cyan-400">{habitation.st_pct}%</div>
              </div>
            </div>
          </div>

          {/* Data Quality & Source Notes */}
          <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
            <span className="flex items-center space-x-1.5">
              <Award className="w-4 h-4 text-slate-500" />
              <span>Location Quality:</span>
            </span>
            <span className="font-mono text-slate-300">{habitation.quality_flags.join(', ') || 'Census Centroid'}</span>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-950/80 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-lg transition-colors"
          >
            Close Details
          </button>
        </div>
      </div>
    </div>
  );
};
