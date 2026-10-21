import React from 'react';
import { Mountain, Map, BarChart3, Target, Compass, BookOpen, Bot, Globe, MessageSquarePlus } from 'lucide-react';
import { TranslationDict } from '../i18n/translations';

interface NavbarProps {
  t: TranslationDict;
  currentTab: string;
  onSelectTab: (tab: string) => void;
  lang: 'en' | 'hi';
  onToggleLang: () => void;
  districtId: number;
  onChangeDistrict: (id: number) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  t,
  currentTab,
  onSelectTab,
  lang,
  onToggleLang,
  districtId,
  onChangeDistrict,
}) => {
  const tabs = [
    { id: 'explorer', label: 'Real data map', icon: Map },
    { id: 'contribute', label: 'Community reports', icon: MessageSquarePlus },
    { id: 'synthetic-map', label: 'Synthetic map', icon: Map },
    { id: 'dashboard', label: `Demo ${t.navDashboard}`, icon: BarChart3 },
    { id: 'siting', label: `Demo ${t.navSiting}`, icon: Target },
    { id: 'scenarios', label: `Demo ${t.navScenarios}`, icon: Compass },
    { id: 'methodology', label: t.navMethodology, icon: BookOpen },
    { id: 'assistant', label: t.navAssistant, icon: Bot },
  ];

  return (
    <header className="site-header bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
      <div className="site-header-inner max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="header-top flex items-center justify-between h-16">
          {/* Logo and Title */}
          <div className="brand-home flex items-center space-x-3 cursor-pointer" onClick={() => onSelectTab('explorer')}>
            <div className="brand-mark w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-green-500 flex items-center justify-center shadow-lg shadow-emerald-900/30">
              <Mountain className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-white">{t.brandName}</span>
                <span className="px-2 py-0.5 text-xs font-medium bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full">v1.1</span>
              </div>
              <p className="text-xs text-slate-400 hidden md:block">Uttarakhand Pilot • Pithoragarh, Chamoli, Rudraprayag</p>
            </div>
          </div>

          {/* District Switcher & Navigation Tabs */}
          <nav className="main-nav hidden lg:flex items-center space-x-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = currentTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => onSelectTab(tab.id)}
                  className={`flex items-center space-x-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-900/30'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>

          {/* District Selector & Language Toggle */}
          <div className="district-controls flex items-center space-x-3">
            <select
              value={districtId}
              onChange={(e) => onChangeDistrict(Number(e.target.value))}
              aria-label={t.filterDistrict}
              className="bg-slate-800 text-slate-200 text-sm font-medium border border-slate-700 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value={1}>Pithoragarh (पिथौरागढ़)</option>
              <option value={2}>Chamoli (चमोली)</option>
              <option value={3}>Rudraprayag (रुद्रप्रयाग)</option>
            </select>

            <button
              onClick={onToggleLang}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm font-medium text-slate-200 transition-colors"
              title="Toggle English / Hindi"
            >
              <Globe className="w-4 h-4 text-emerald-400" />
              <span>{lang === 'en' ? 'हिन्दी' : 'English'}</span>
            </button>
          </div>
        </div>

        {/* Mobile Nav */}
        <nav aria-label="Main navigation" className="mobile-nav flex lg:hidden overflow-x-auto py-2 space-x-1 border-t border-slate-800/60">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-md text-xs font-medium whitespace-nowrap ${
                  isActive ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
