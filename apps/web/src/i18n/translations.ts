export interface TranslationDict {
  brandName: string;
  brandTagline: string;
  navExplorer: string;
  navDashboard: string;
  navSiting: string;
  navScenarios: string;
  navMethodology: string;
  navAssistant: string;
  filterDistrict: string;
  filterTier: string;
  filterThreshold: string;
  filterMode: string;
  filterObjective: string;
  modeWalkOnly: string;
  modeHybrid: string;
  tierAll: string;
  objMaxCoverage: string;
  objEquity: string;
  objMinMeanTime: string;
  kpiTotalPop: string;
  kpiUnderservedPop: string;
  kpiUnderservedHabs: string;
  kpiMeanTime: string;
  kpiMedianTime: string;
  kpiFacilities: string;
  legendTitle: string;
  legendUnder30: string;
  legend30to60: string;
  legend60to90: string;
  legendOver90: string;
  disclaimer: string;
  candidateBadge: string;
  villageDetailsTitle: string;
  population: string;
  scStShare: string;
  nearestFacility: string;
  travelTimeRange: string;
  qualityFlag: string;
  askAssistantPlaceholder: string;
  sendQuery: string;
  citations: string;
  newFacilitySite: string;
  gainPopulation: string;
  timeSavings: string;
  equityGain: string;
}

export const translations: Record<'en' | 'hi', TranslationDict> = {
  en: {
    brandName: 'HillCare Access',
    brandTagline: 'Slope-adjusted health facility access & siting for Himalayan districts',
    navExplorer: 'Explorer Map',
    navDashboard: 'District Dashboard',
    navSiting: 'Siting Optimizer',
    navScenarios: 'Scenario Workspace',
    navMethodology: 'Methodology',
    navAssistant: 'AI Planner Assistant',
    filterDistrict: 'Pilot District',
    filterTier: 'Facility Tier',
    filterThreshold: 'Walking Threshold',
    filterMode: 'Travel Mode',
    filterObjective: 'Siting Objective',
    modeWalkOnly: 'Walk Only (Physical Isolation)',
    modeHybrid: 'Hybrid (Walk + Hill Road Vehicle)',
    tierAll: 'All Facilities (HWC, PHC, CHC, DH)',
    objMaxCoverage: 'Max Newly Covered Population',
    objEquity: 'Equity-Weighted (SC/ST Priority)',
    objMinMeanTime: 'Minimize Mean Walking Time',
    kpiTotalPop: 'Total District Population',
    kpiUnderservedPop: 'Underserved Population',
    kpiUnderservedHabs: 'Underserved Villages',
    kpiMeanTime: 'Mean Walking Time',
    kpiMedianTime: 'Median Walking Time',
    kpiFacilities: 'Functional Facilities',
    legendTitle: 'Walking Time to Care',
    legendUnder30: '≤ 30 min (Norm Compliant)',
    legend30to60: '30 - 60 min (Moderate)',
    legend60to90: '60 - 90 min (High Isolation)',
    legendOver90: '> 90 min (Critical Underserved)',
    disclaimer: 'Notice: Measures realistic slope-adjusted walking accessibility on terrain. Does not measure clinical staffing, quality, or unmet health need.',
    candidateBadge: 'Optimal Candidate',
    villageDetailsTitle: 'Village Accessibility Details',
    population: 'Population',
    scStShare: 'SC / ST Demographic Share',
    nearestFacility: 'Nearest Functional Facility',
    travelTimeRange: 'Walking Time (Uncertainty Range)',
    qualityFlag: 'Centroid Quality',
    askAssistantPlaceholder: 'Ask in English or Hindi (e.g. How many people in Pithoragarh are underserved? / IPHS standards)...',
    sendQuery: 'Ask Assistant',
    citations: 'Grounded Sources & Citations',
    newFacilitySite: 'New Facility Candidate',
    gainPopulation: 'Newly Covered Population',
    timeSavings: 'Mean Time Reduction',
    equityGain: 'Equity Score',
  },
  hi: {
    brandName: 'हिलकेयर एक्सेस',
    brandTagline: 'पर्वतीय जिलों हेतु ढलान-समायोजित स्वास्थ्य सुविधा पहुंच और स्थान चयन',
    navExplorer: 'मानचित्र अन्वेषक',
    navDashboard: 'जिला डैशबोर्ड',
    navSiting: 'स्थान चयन अनुकूलक',
    navScenarios: 'परिदृश्य कार्यक्षेत्र',
    navMethodology: 'कार्यप्रणाली',
    navAssistant: 'एआई स्वास्थ्य सहायक',
    filterDistrict: 'पायलट जिला',
    filterTier: 'सुविधा स्तर',
    filterThreshold: 'पैदल यात्रा सीमा',
    filterMode: 'यात्रा माध्यम',
    filterObjective: 'स्थान चयन लक्ष्य',
    modeWalkOnly: 'केवल पैदल (भौगोलिक पृथक्करण)',
    modeHybrid: 'मिश्रित (पैदल + पहाड़ी सड़क वाहन)',
    tierAll: 'सभी सुविधाएं (HWC, PHC, CHC, DH)',
    objMaxCoverage: 'अधिकतम नई जनसंख्या कवरेज',
    objEquity: 'समानता-भारित (SC/ST प्राथमिकता)',
    objMinMeanTime: 'औसत पैदल समय में कमी',
    kpiTotalPop: 'जिले की कुल जनसंख्या',
    kpiUnderservedPop: 'सुविधाहीन जनसंख्या',
    kpiUnderservedHabs: 'सुविधाहीन गांव',
    kpiMeanTime: 'औसत पैदल समय',
    kpiMedianTime: 'माध्यिका पैदल समय',
    kpiFacilities: 'क्रियाशील स्वास्थ्य केंद्र',
    legendTitle: 'स्वास्थ्य केंद्र तक पैदल समय',
    legendUnder30: '≤ 30 मिनट (मानक अनुसार)',
    legend30to60: '30 - 60 मिनट (मध्यम)',
    legend60to90: '60 - 90 मिनट (कठिन पहुंच)',
    legendOver90: '> 90 मिनट (अति दुर्गम/सुविधाहीन)',
    disclaimer: 'सूचना: यह ढलान-समायोजित वास्तविक पैदल पहुंच को मापता है। यह नैदानिक गुणवत्ता अथवा दवा उपलब्धता का आकलन नहीं करता।',
    candidateBadge: 'अनुशंसित नया केंद्र',
    villageDetailsTitle: 'गांव की स्वास्थ्य पहुंच विवरण',
    population: 'जनसंख्या',
    scStShare: 'अनुसूचित जाति/जनजाति हिस्सा',
    nearestFacility: 'निकटतम क्रियाशील स्वास्थ्य केंद्र',
    travelTimeRange: 'पैदल समय (अनिश्चितता दायरा)',
    qualityFlag: 'स्थान प्रमाणिकता',
    askAssistantPlaceholder: 'अंग्रेजी या हिंदी में पूछें (उदा: पिथौरागढ़ में कितने लोग सुविधाहीन हैं? / IPHS मानक)...',
    sendQuery: 'सहायक से पूछें',
    citations: 'प्रमाणित स्रोत एवं उद्धरण',
    newFacilitySite: 'प्रस्तावित नया स्वास्थ्य केंद्र',
    gainPopulation: 'नई आच्छादित जनसंख्या',
    timeSavings: 'समय की औसत बचत',
    equityGain: 'समानता स्कोर',
  },
};
