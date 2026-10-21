import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { MapExplorer } from './components/MapExplorer';
import { RealDataExplorer } from './components/RealDataExplorer';
import { CommunityReportsWorkspace } from './components/CommunityReportsWorkspace';
import { DistrictDashboard } from './components/DistrictDashboard';
import { SitingOptimizerView } from './components/SitingOptimizerView';
import { ScenarioWorkspace } from './components/ScenarioWorkspace';
import { MethodologyView } from './components/MethodologyView';
import { AssistantPanel } from './components/AssistantPanel';
import { VillageDetailModal } from './components/VillageDetailModal';
import { translations } from './i18n/translations';
import { CandidateItem, FacilityItem, HabitationItem, RegionSummary } from './types';
import {
  fetchCandidates,
  fetchFacilities,
  fetchHabitations,
  fetchRegionSummary,
} from './services/api';

const DISTRICT_NAMES: Record<number, string> = {
  1: 'Pithoragarh',
  2: 'Chamoli',
  3: 'Rudraprayag',
};

export const App: React.FC = () => {
  const [lang, setLang] = useState<'en' | 'hi'>('en');
  const [currentTab, setCurrentTab] = useState<string>('explorer');
  const [districtId, setDistrictId] = useState<number>(1);

  // Data states
  const [summary, setSummary] = useState<RegionSummary | null>(null);
  const [habitations, setHabitations] = useState<HabitationItem[]>([]);
  const [facilities, setFacilities] = useState<FacilityItem[]>([]);
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Selected village for modal
  const [selectedHabitation, setSelectedHabitation] = useState<HabitationItem | null>(null);

  const t = translations[lang];
  const districtName = DISTRICT_NAMES[districtId] || 'Pithoragarh';

  // Load district datasets on districtId change
  useEffect(() => {
    if (!['synthetic-map', 'dashboard', 'siting'].includes(currentTab)) return;
    let isMounted = true;
    async function loadData() {
      setLoading(true);
      try {
        const [sumData, habData, facData, candData] = await Promise.all([
          fetchRegionSummary(districtId).catch(() => null),
          fetchHabitations(districtId, 250).catch(() => ({ total_count: 0, items: [] })),
          fetchFacilities(districtId).catch(() => []),
          fetchCandidates(districtName).catch(() => []),
        ]);

        if (isMounted) {
          setSummary(sumData);
          setHabitations(habData.items || []);
          setFacilities(facData || []);
          setCandidates(candData || []);
        }
      } catch (err) {
        console.error('Error loading district access data:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [currentTab, districtId, districtName]);

  const handleSelectCandidate = (_cand: CandidateItem) => {
    // Switch to map view to inspect the candidate
    setCurrentTab('synthetic-map');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        t={t}
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        lang={lang}
        onToggleLang={() => setLang(lang === 'en' ? 'hi' : 'en')}
        districtId={districtId}
        onChangeDistrict={setDistrictId}
      />

      <main className="flex-1">
        {currentTab === 'explorer' && (
          <RealDataExplorer district={districtName} />
        )}

        {currentTab === 'contribute' && <CommunityReportsWorkspace district={districtName} />}

        {currentTab === 'synthetic-map' && (
          <>
            <div className="demo-mode-banner">SYNTHETIC DEMO · Uses sample database records and generated terrain/modifiers. This is not the real-data map.</div>
            <MapExplorer
              t={t}
              habitations={habitations}
              facilities={facilities}
              candidates={candidates}
              selectedDistrictName={districtName}
              onSelectHabitation={setSelectedHabitation}
              onSelectCandidate={handleSelectCandidate}
            />
          </>
        )}

        {currentTab === 'dashboard' && (
          <>
            <div className="demo-mode-banner">SYNTHETIC/DEMO SUMMARY · This view uses the existing sample database, not the real-data geographic access analysis.</div>
            <DistrictDashboard summary={summary} habitations={habitations} t={t} />
          </>
        )}

        {currentTab === 'siting' && (
          <>
            <div className="demo-mode-banner">SYNTHETIC/DEMO SITING · Recommendations use the existing sample pipeline.</div>
            <SitingOptimizerView
              candidates={candidates}
              summary={summary}
              t={t}
              selectedDistrictName={districtName}
              onSelectCandidate={handleSelectCandidate}
            />
          </>
        )}

        {currentTab === 'scenarios' && (
          <>
            <div className="demo-mode-banner">SYNTHETIC/DEMO SCENARIO · Scenario results use the sample database and current demo pipeline.</div>
            <ScenarioWorkspace
              districtId={districtId}
              selectedDistrictName={districtName}
              t={t}
            />
          </>
        )}

        {currentTab === 'methodology' && <MethodologyView t={t} />}

        {currentTab === 'assistant' && (
          <>
            <div className="demo-mode-banner">DEMO ASSISTANT · Any live statistics shown come from the existing sample database.</div>
            <AssistantPanel
              districtId={districtId}
              selectedDistrictName={districtName}
              lang={lang}
              t={t}
            />
          </>
        )}
      </main>

      {/* Village Details Modal */}
      <VillageDetailModal
        habitation={selectedHabitation}
        onClose={() => setSelectedHabitation(null)}
        t={t}
      />
    </div>
  );
};

export default App;
