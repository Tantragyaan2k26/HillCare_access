import React, { useState } from 'react';
import {
  Bot,
  Send,
  Sparkles,
  BookOpen,
  Link2,
  AlertCircle,
  HelpCircle,
  Loader2,
  CheckCircle,
} from 'lucide-react';
import { askAssistant } from '../services/api';
import { AssistantResponse } from '../types';
import { TranslationDict } from '../i18n/translations';

interface AssistantPanelProps {
  districtId: number;
  selectedDistrictName: string;
  lang: 'en' | 'hi';
  t: TranslationDict;
}

export const AssistantPanel: React.FC<AssistantPanelProps> = ({
  districtId,
  selectedDistrictName,
  lang,
  t,
}) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversation, setConversation] = useState<AssistantResponse[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const sampleQuestions = [
    {
      en: `How many people in ${selectedDistrictName} are underserved (>60 min)?`,
      hi: `${selectedDistrictName} में कितने लोग 60 मिनट से अधिक की दूरी पर हैं?`,
    },
    {
      en: 'What are the IPHS 2022 population norms for hilly and tribal areas?',
      hi: 'पहाड़ी और जनजातीय क्षेत्रों के लिए IPHS 2022 के जनसंख्या मानक क्या हैं?',
    },
    {
      en: "How does Waldo Tobler's Hiking Function compute slope-adjusted speed?",
      hi: 'टोबलर का हाइकिंग फॉर्मूला ढलान के अनुसार पैदल गति कैसे मापता है?',
    },
    {
      en: 'How does Sentinel-1 SAR detect monsoon landslide blockages?',
      hi: 'सेंटिनल-1 सार रडार मानसून में भूस्खलन का पता कैसे लगाता है?',
    },
  ];

  const handleSend = async (qToSend?: string) => {
    const text = qToSend || query;
    if (!text.trim()) return;

    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await askAssistant(text, lang, districtId);
      setConversation((prev) => [res, ...prev]);
      setQuery('');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to get assistant response');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-1">
          <Bot className="w-4 h-4" />
          <span>AI Health Planner Assistant (RAG Engine v1.1)</span>
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">{t.navAssistant}</h1>
        <p className="text-sm text-slate-400 mt-1">
          Ask questions in English or Hindi grounded in IPHS guidelines, NHM policies, and live district model runs.
        </p>
      </div>

      {/* Suggested Prompts */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Suggested Questions:</span>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {sampleQuestions.map((sq, i) => {
            const promptText = lang === 'hi' ? sq.hi : sq.en;
            return (
              <button
                key={i}
                onClick={() => handleSend(promptText)}
                className="text-left p-3 rounded-xl bg-slate-900 border border-slate-800 hover:border-emerald-600/50 hover:bg-slate-800/80 text-xs text-slate-300 transition-all flex items-center justify-between"
              >
                <span>{promptText}</span>
                <Sparkles className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 ml-2" />
              </button>
            );
          })}
        </div>
      </div>

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="relative"
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t.askAssistantPlaceholder}
          className="w-full bg-slate-900 border border-slate-700 rounded-2xl py-3.5 pl-4 pr-32 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 shadow-xl"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="absolute right-2 top-2 bottom-2 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-white font-semibold text-xs rounded-xl flex items-center space-x-1.5 transition-colors shadow-md"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          <span>{t.sendQuery}</span>
        </button>
      </form>

      {errorMsg && (
        <div className="p-3 bg-red-950/60 border border-red-800 text-red-300 text-xs rounded-lg flex items-center space-x-2">
          <AlertCircle className="w-4 h-4" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Conversation Stream */}
      <div className="space-y-6 pt-2">
        {conversation.map((item, idx) => (
          <div key={idx} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            {/* User Question */}
            <div className="flex items-start space-x-3 text-sm font-semibold text-white border-b border-slate-800 pb-3">
              <span className="w-6 h-6 rounded-full bg-emerald-950 border border-emerald-800 text-emerald-400 flex items-center justify-center text-xs flex-shrink-0">
                Q
              </span>
              <span>{item.query}</span>
            </div>

            {/* Answer */}
            <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-line pl-9">
              {item.answer}
            </div>

            {/* Citations & Evidence Grounding */}
            {item.citations.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-800/80 pl-9 space-y-2">
                <div className="flex items-center space-x-1.5 text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>{t.citations}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {item.citations.map((cite, cIdx) => (
                    <div key={cIdx} className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs space-y-1">
                      <div className="font-bold text-white truncate">{cite.source_title}</div>
                      {cite.section && <div className="text-[11px] text-emerald-400">{cite.section}</div>}
                      <p className="text-[11px] text-slate-400 italic">"{cite.quote}"</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tool Calls Executed */}
            {item.tool_calls_executed.length > 0 && (
              <div className="pl-9 flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
                <span>Tools executed:</span>
                <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-slate-400">
                  {item.tool_calls_executed.join(', ')}
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
