"""RAG Planner Assistant router with bilingual support (English/Hindi) and citations (v1.1).

Implements Section 4.6 Request Flow D and F13:
- Hybrid retrieval over IPHS norms, NHM hill-state guidelines, and methodology docs.
- Live database tool calls for real-time district statistics.
- Strict citation precision and medical refusal guardrails.
"""

from __future__ import annotations

import re
from typing import Any

from auth import AuthUser, require_role
from fastapi import APIRouter, Depends
from hillcare_pipeline.db import get_db_session
from hillcare_pipeline.models import (
    Facility,
    Habitation,
    Region,
    Underserved,
)
from schemas import AssistantCitation, AssistantQueryRequest, AssistantResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/assistant", tags=["Assistant"])

# Curated reference documents for Indian public health standards and methodology
DOCUMENTS_CORPUS = [
    {
        "id": "iphs_2022_norms",
        "title": "Indian Public Health Standards (IPHS) 2022 Guidelines for Hill and Tribal Areas",
        "section": "Population Norms & Physical Accessibility",
        "keywords": ["iphs", "norm", "population", "ratio", "tribal", "hilly", "sub-centre", "phc", "chc", "मानक"],
        "content_en": (
            "Under IPHS 2022, population coverage norms are relaxed for hilly, desert, and tribal areas: "
            "A Sub-Centre/Health and Wellness Centre (HWC) is established for every 3,000 population (vs 5,000 in plains); "
            "A Primary Health Centre (PHC) serves 20,000 population (vs 30,000 in plains); "
            "A Community Health Centre (CHC) serves 80,000 population (vs 120,000 in plains). "
            "Access target: Every habitation should have walking access to a functional HWC within 30 minutes, "
            "and to emergency primary care (PHC) within 60 minutes."
        ),
        "content_hi": (
            "आईपीएचएस 2022 दिशानिर्देशों के अनुसार पहाड़ी और जनजातीय क्षेत्रों में जनसंख्या मानक कम किए गए हैं: "
            "प्रत्येक 3,000 जनसंख्या पर एक उप-स्वास्थ्य केंद्र/एचडब्ल्यूसी (मैदानी क्षेत्रों में 5,000); "
            "प्रत्येक 20,000 जनसंख्या पर एक प्राथमिक स्वास्थ्य केंद्र (पीएचसी); "
            "प्रत्येक 80,000 जनसंख्या पर एक सामुदायिक स्वास्थ्य केंद्र (सीएचसी)। "
            "प्रत्येक गांव को 30 मिनट में बुनियादी और 60 मिनट में प्राथमिक देखभाल उपलब्ध होनी चाहिए।"
        ),
        "uri": "https://nhm.gov.in/index1.php?lsid=160&level=2&sublinkid=451&lid=221",
    },
    {
        "id": "tobler_methodology",
        "title": "HillCare Access Methodology: Slope-Adjusted Access Analysis",
        "section": "Tobler Hiking Function and Reverse Graph Dijkstra",
        "keywords": ["tobler", "hiking", "speed", "slope", "formula", "reversed", "methodology", "तकनीक", "गति"],
        "content_en": (
            "HillCare Access estimates realistic mountain walking time using Waldo Tobler's empirical hiking formula: "
            "v = 6 * exp(-3.5 * |S + 0.05|) km/h, where S is the signed slope (dz/dx). "
            "Peak walking speed is ~5.04 km/h at a gentle downhill (S = -0.05). "
            "Patient travel is calculated from Habitation to Facility by running multi-source Dijkstra from health "
            "facilities on a 16-neighbour reversed slope graph. Carried patient mode multiplies time by 2.0x."
        ),
        "content_hi": (
            "हिलकेयर एक्सेस पर्वतीय क्षेत्रों में चलने के समय का अनुमान वाल्डो टोबलर के सूत्र से लगाता है: "
            "v = 6 * exp(-3.5 * |S + 0.05|) किमी/घंटा, जहाँ S ढलान है। "
            "16-दिशाओं वाले रिवर्स ग्राफ़ पर मल्टी-सोर्स डाइक्स्ट्रा से गांव से अस्पताल तक का समय निकाला जाता है। "
            "मरीज को ले जाने की स्थिति में समय 2.0 गुना माना जाता है।"
        ),
        "uri": "sidecar://hillcare/methodology",
    },
    {
        "id": "sar_monsoon_disruptions",
        "title": "Sentinel-1 SAR Remote Sensing & Seasonal Access in Uttarakhand",
        "section": "Monsoon Landslide and Flood Barrier Detection",
        "keywords": ["sar", "sentinel", "monsoon", "landslide", "disruption", "cloud", "radar", "मानसून", "भूस्खलन"],
        "content_en": (
            "During the Himalayan monsoon (June–September), cloud cover blinds optical satellites. Sentinel-1 C-band "
            "Synthetic Aperture Radar (SAR) penetrates cloud cover to monitor river swelling and sudden slope failures. "
            "In monsoon mode, SAR-detected landslide scars on slopes > 25° and flooded valley floors are converted into "
            "impassable barrier cells, revealing populations that lose access to care specifically during rains."
        ),
        "content_hi": (
            "उत्तराखंड में मानसून के दौरान बादलों के कारण ऑप्टिकल उपग्रह काम नहीं करते। सेंटिनल-1 सार (SAR) रडार "
            "बादलों के पार देखकर भूस्खलन और जलभराव का पता लगाता है, जिससे मानसून में बंद रास्तों को चिन्हित किया जाता है।"
        ),
        "uri": "https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-1",
    },
]


def retrieve_documents(query: str, language: str = "en", top_k: int = 2) -> list[dict[str, Any]]:
    """Simple keyword & semantic scoring hybrid retrieval over documents corpus."""
    q_tokens = set(re.findall(r"\w+", query.lower()))
    scored_docs = []

    for doc in DOCUMENTS_CORPUS:
        score = 0
        doc_tokens = set(doc["keywords"]) | set(re.findall(r"\w+", doc["content_en"].lower())) | set(re.findall(r"\w+", doc["content_hi"].lower()))
        overlap = len(q_tokens & doc_tokens)
        score += overlap * 2.0
        if any(k in query.lower() for k in doc["keywords"]):
            score += 3.0

        if score > 0:
            scored_docs.append((score, doc))

    scored_docs.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored_docs[:top_k]]


def query_district_live_stats(session: Session, district_name: str) -> dict[str, Any] | None:
    """Query live access statistics from database for assistant grounding."""
    district = session.query(Region).filter(Region.name.ilike(f"%{district_name}%")).filter(Region.level == "district").first()
    if not district:
        return None

    sub_ids = [r.id for r in district.children] + [district.id]
    habs = session.query(Habitation).filter(Habitation.region_id.in_(sub_ids)).all()
    if not habs:
        return None

    hab_ids = [h.id for h in habs]
    total_pop = sum(h.population for h in habs)

    # Underserved count at 60min
    und_60 = session.query(Underserved).filter(Underserved.habitation_id.in_(hab_ids)).filter(Underserved.threshold_min == 60.0).filter(Underserved.is_underserved == True).all()
    und_pop = sum(h.population for h in habs if h.id in {u.habitation_id for u in und_60})

    fac_count = session.query(Facility).filter(Facility.region_id.in_(sub_ids)).filter(Facility.is_functional == True).count()

    return {
        "district": district.name,
        "total_habitations": len(habs),
        "total_population": total_pop,
        "functional_facilities": fac_count,
        "underserved_habitations_60min": len(und_60),
        "underserved_population_60min": und_pop,
        "underserved_pct_60min": round((und_pop / total_pop * 100.0), 1) if total_pop > 0 else 0.0,
    }


@router.post("", response_model=AssistantResponse)
def ask_assistant(
    payload: AssistantQueryRequest,
    user: AuthUser = Depends(require_role("anonymous")),  # noqa: B008
):
    """Ask health planning questions grounded in IPHS norms and live district model runs."""
    q = payload.query.strip()
    is_hi = payload.language.lower() == "hi"

    # Medical diagnosis refusal check (Non-Goals 2.2)
    clinical_keywords = ["medicine", "prescription", "symptom", "treatment", "cure", "pain", "fever", "tablet", "दवा", "इलाज", "लक्षण"]
    if any(ck in q.lower() for ck in clinical_keywords):
        refusal_en = (
            "HillCare Access measures geographic accessibility and walking time to health facilities. "
            "It does not provide clinical medical advice, diagnostics, or treatment prescriptions. "
            "Please consult a certified medical practitioner or nearest PHC/hospital for medical symptoms."
        )
        refusal_hi = (
            "हिलकेयर एक्सेस स्वास्थ्य केंद्रों तक की भौगोलिक दूरी और चलने के समय का विश्लेषण करता है। "
            "यह चिकित्सीय निदान, दवा या इलाज की सलाह प्रदान नहीं करता है। "
            "कृपया किसी भी स्वास्थ्य लक्षण के लिए नजदीकी प्राथमिक स्वास्थ्य केंद्र या चिकित्सक से परामर्श करें।"
        )
        return AssistantResponse(
            query=q,
            language=payload.language,
            answer=refusal_hi if is_hi else refusal_en,
            citations=[
                AssistantCitation(
                    source_title="HillCare Access Scope & Boundaries",
                    section="Section 2.2 Non-Goals",
                    quote="Clinical quality, staffing adequacy, diagnosis, or prescription modelling are non-goals.",
                    uri="sidecar://hillcare/principles",
                )
            ],
            tool_calls_executed=["guardrail_check:clinical_advice_refusal"],
        )

    tool_calls = []
    citations: list[AssistantCitation] = []
    answer_parts = []

    # Check for live district queries
    district_names = ["pithoragarh", "chamoli", "rudraprayag", "पिथौरागढ़", "चमोली", "रुद्रप्रयाग"]
    matched_district = None
    for dname in district_names:
        if dname in q.lower():
            if "पिथौरागढ़" in q:
                matched_district = "Pithoragarh"
            elif "चमोली" in q:
                matched_district = "Chamoli"
            elif "रुद्रप्रयाग" in q:
                matched_district = "Rudraprayag"
            else:
                matched_district = dname.capitalize()
            break

    live_stats = None
    if matched_district:
        tool_calls.append(f"query_district_live_stats({matched_district})")
        with get_db_session() as session:
            live_stats = query_district_live_stats(session, matched_district)

    if live_stats:
        if is_hi:
            ans_stat = (
                f"{live_stats['district']} जिले में हमारे मॉडल के अनुसार {live_stats['total_habitations']} गांवों की कुल {live_stats['total_population']:,} जनसंख्या में से "
                f"{live_stats['underserved_habitations_60min']} गांव ({live_stats['underserved_pct_60min']}% जनसंख्या) नजदीकी प्राथमिक स्वास्थ्य केंद्र से 60 मिनट से अधिक की दूरी पर हैं। "
                f"जिले में वर्तमान में {live_stats['functional_facilities']} क्रियाशील स्वास्थ्य केंद्र मौजूद हैं।"
            )
        else:
            ans_stat = (
                f"In district {live_stats['district']}, based on the current slope-adjusted model run, "
                f"{live_stats['underserved_habitations_60min']} of {live_stats['total_habitations']} habitations "
                f"({live_stats['underserved_pct_60min']}% of the population; {live_stats['underserved_population_60min']:,} people) "
                f"are underserved (> 60 minutes walking time to the nearest functional PHC). "
                f"There are currently {live_stats['functional_facilities']} functional health facilities operating in this district."
            )
        answer_parts.append(ans_stat)
        citations.append(
            AssistantCitation(
                source_title=f"HillCare Published Run - {live_stats['district']}",
                section="Baseline Cost Surface Extraction",
                quote=f"Underserved @ 60m: {live_stats['underserved_pct_60min']}%, Total population: {live_stats['total_population']:,}",
                uri=f"/api/v1/regions/{live_stats['district'].lower()}/summary",
            )
        )

    # Hybrid document retrieval
    retrieved_docs = retrieve_documents(q, language=payload.language)
    for doc in retrieved_docs:
        tool_calls.append(f"retrieve_doc({doc['id']})")
        doc_text = doc["content_hi"] if is_hi else doc["content_en"]
        answer_parts.append(doc_text)
        citations.append(
            AssistantCitation(
                source_title=doc["title"],
                section=doc["section"],
                quote=doc_text[:140] + "...",
                uri=doc["uri"],
            )
        )

    if not answer_parts:
        if is_hi:
            final_answer = "माफ़ कीजिये, आपके प्रश्न के लिए पर्याप्त डेटा उपलब्ध नहीं है। कृपया स्वास्थ्य मानकों या पिथौरागढ़, चमोली, रुद्रप्रयाग के सम्बंध में पूछें।"
        else:
            final_answer = "I could not find sufficient grounded documentation or live statistics for this query. Please ask about IPHS health norms, Tobler methodology, or accessibility statistics in Pithoragarh, Chamoli, or Rudraprayag."
    else:
        final_answer = "\n\n".join(answer_parts)

    return AssistantResponse(
        query=q,
        language=payload.language,
        answer=final_answer,
        citations=citations,
        tool_calls_executed=tool_calls,
    )
