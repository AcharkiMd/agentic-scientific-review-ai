"""Specialist-agent functions: planning, strategy, dual screening, appraisal, synthesis, QA.

Gemini mode uses structured generation; demo mode is explicitly deterministic and
synthetic. No generated 'fact' is trusted until its source is recorded.
"""
from __future__ import annotations
import re
from datetime import date
from typing import Any


def obj(properties: dict, required: list[str] | None = None) -> dict:
    return {"type":"object","properties":properties,"required":required or list(properties)}

S = {"type":"string"}
A = {"type":"array", "items":S}


def validate_protocol(p: dict):
    for field in ("research_question","objective","inclusion_criteria","exclusion_criteria","databases"):
        if not p.get(field):
            raise ValueError(f"Missing required protocol field: {field}")
    if not isinstance(p["inclusion_criteria"],list) or not isinstance(p["exclusion_criteria"],list):
        raise ValueError("Protocol criteria must be lists")
    if not 1 <= int(p.get("max_papers",12)) <= 100:
        raise ValueError("max_papers must be between 1 and 100")


def plan(provider, topic: str, max_papers: int) -> dict:
    if provider.mode == "demo":
        protocol = {
            "research_question": f"What does the research show about {topic.rstrip('?')}?",
            "objective": "Summarize methods, results, and limitations of relevant research.",
            "inclusion_criteria":["Related to topic", "Research study with usable methodological evidence"],
            "exclusion_criteria":["Unrelated to topic", "Insufficient usable study evidence"],
            "databases":["Synthetic fixture only (NO real literature searches)"],
            "publication_year_start": 2018,"publication_year_end": date.today().year,
            "language":"English", "max_papers":max_papers,"version":"1.0-demo",
            "method":"PRISMA-aligned teaching prototype; simulated screening"
        }
    else:
        p = provider.generate_json("Protocol Planner Agent",
            "Generate a general-purpose PRISMA-aligned review protocol. Specify inclusion and exclusion "
            f"criteria applicable to this question: {topic}. Avoid claiming a protocol was preregistered.",
            obj({"research_question":S,"objective":S,"inclusion_criteria":A,
                 "exclusion_criteria":A,"language":S,"publication_year_start":{"type":"integer"}}))
        protocol = {**p,"databases":["OpenAlex","arXiv"],"publication_year_end":date.today().year,
                    "max_papers":max_papers,"version":"1.0",
                    "method":"PRISMA-aligned prototype; human-reviewed protocol; not preregistered"}
    validate_protocol(protocol)
    return protocol


def strategy(provider, protocol: dict) -> list[str]:
    topic = protocol["research_question"]
    if provider.mode == "demo":
        return ["lakehouse big data analytics", "scalable lakehouse query optimization"]
    p = provider.generate_json("Search Strategy Agent",
        "Provide two short, independently useful scholarly API search queries. OpenAlex works supports "
        "Boolean operators. arXiv will use all:<query> syntax; keep search terms short and literal. "
        f"Question: {topic}. Inclusion criteria: {protocol['inclusion_criteria']}",
        obj({"queries":{"type":"array","items":S}}))
    queries = [str(q).strip()[:200] for q in p.get("queries",[]) if str(q).strip()]
    if not queries:
        raise ValueError("Search Strategy Agent returned no queries")
    return queries[:3]


def _demo_vote(paper: dict, strict: bool = False) -> dict:
    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "").lower()
    # Lexical, intentionally simplistic; relevant only to the fixed synthetic fixture.
    good = "lakehouse" in title and (not strict or any(x in abstract for x in ("query", "scalable", "analytics", "data")))
    verdict = "include" if good else "exclude"
    return {"decision":verdict,
            "rationale": "Synthetic fixture lexical relevance check; not a scientific judgement",
            "evidence": paper.get("title", "")[:180]}


def _vote(provider, paper: dict, protocol: dict, stage: str, reviewer: int) -> dict:
    if provider.mode == "demo":
        return _demo_vote(paper,strict=(reviewer==2))
    material = (paper.get("title","")+"\n"+
                (paper.get("full_text","")[:16000] if stage == "fulltext" else paper.get("abstract","")))
    if not material.strip() or (stage == "title" and not paper.get("abstract")):
        return {"decision":"uncertain","rationale":"Insufficient text for screening", "evidence":""}
    d = provider.generate_json(f"Independent {stage} Screening Reviewer {reviewer}",
        f"Read only the supplied scholarly record. Independently decide include/exclude/uncertain "
        f"under the registered protocol. Do not infer missing full text. "
        f"Protocol: {protocol}. Record: {material}",
        obj({"decision":{"type":"string","enum":["include","exclude","uncertain"]},
             "rationale":S,"evidence":S}))
    if d.get("decision") not in {"include","exclude","uncertain"}:
        raise ValueError("Screening agent returned an invalid decision")
    return d


def screen(provider, papers: list[dict], protocol: dict, stage: str) -> list[dict]:
    if stage not in {"title", "fulltext"}:
        raise ValueError("Invalid screening stage")
    out = []
    for p in papers:
        if stage == "fulltext" and not p.get("full_text"):
            out.append({"paper_id":p["id"],"decision":"not_assessed_missing_fulltext",
                        "rationale":"Full text not available; abstract-only evidence cannot be called full-text screened",
                        "reviewers":[],"conflict":False,"stage":stage})
            continue
        a = _vote(provider,p,protocol,stage,1)
        b = _vote(provider,p,protocol,stage,2)
        agree = a["decision"] == b["decision"]
        final = a["decision"] if agree else "uncertain"
        out.append({"paper_id":p["id"],"decision":final,
                    "rationale": a["rationale"] if agree else "Disagreement; requires human resolution",
                    "reviewers":[a,b],"conflict":not agree,"stage":stage})
    return out


def extract(provider, paper: dict) -> dict:
    if not paper.get("full_text"):
        raise ValueError("Cannot extract full-text evidence from missing PDF")
    text = paper["full_text"][:18000]
    if provider.mode == "demo":
        # A selected verbatim sentence as a traceable evidence snippet.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+",text) if len(s.strip())>30]
        quote = sentences[0][:250] if sentences else text[:200]
        response = {"study_design":"synthetic illustrative experiment/methods",
                    "methods":"See quoted fixture passage; demo rule-based extraction",
                    "findings":quote,"limitations":"Synthetic fixture; no real scientific validity",
                    "risk_of_bias":"unclear","evidence_quote":quote}
    else:
        response = provider.generate_json("Evidence Extraction and Appraisal Agent",
            "Extract study-level evidence ONLY from the full text shown, including an EXACT "
            "short quotation supporting the main finding. Describe the research design, methods, "
            "reported results and limitations. Assign an approximate generic methodological "
            "concern rating (low/moderate/high/unclear), not a validated risk-of-bias judgement. "
            "Do not infer statistics or effects. If the necessary detail is missing, say 'not reported'. "
            f"Paper ID: {paper['id']}; title: {paper['title']}; FULL TEXT:\n{text}",
            obj({"study_design":S,"methods":S,"findings":S,"limitations":S,
                 "risk_of_bias":{"type":"string","enum":["low","moderate","high","unclear"]},
                 "evidence_quote":S}))
    quote = str(response.get("evidence_quote", ""))
    # Verbatim quote is the only automatic verification; semantics require human validation.
    supported = bool(quote and re.sub(r"\s+"," ",quote).strip() in re.sub(r"\s+"," ",text))
    return {"paper_id":paper["id"],"title":paper["title"],"year":paper.get("year"),
            **response,"evidence_supported":supported,"source_scope":"fulltext",
            "source_id":paper["id"]}


def synthesize(provider, protocol: dict, extractions: list[dict], rag_hits: list[dict]) -> dict:
    if not extractions:
        return {"overview":"No papers passed full-text screening. No evidence-based synthesis is possible.",
                "themes":[],"limitations":"Do not infer findings from excluded or unavailable reports."}
    if provider.mode == "demo":
        return {"overview":"Synthetic evidence suggests that lakehouse scaling, query layout and table maintenance are study themes; all sample data are fabricated.",
                "themes":[{"name":"Lakehouse architecture and query execution",
                           "summary":"The fixture contains illustrative methods and fictional comparative results.",
                           "paper_ids":[e["paper_id"] for e in extractions]}],
                "limitations":"ALL fixture publications and numerical claims are synthetic and must not be cited as real research."}
    valid_ids = [x["paper_id"] for x in extractions]
    compact = [{k:v for k,v in e.items() if k in ("paper_id","study_design","findings","limitations","evidence_quote","evidence_supported")}
               for e in extractions]
    result = provider.generate_json("Synthesis and Scientific Writing Agent",
        "Produce a cautious narrative synthesis ONLY of these full-text-screened extracted records "
        "and supporting retrieved passages. Avoid quantitative pooled meta-analysis unless comparable "
        "effect sizes and uncertainties exist. Cite ONLY the exact provided paper_ids in the thematic "
        "paper_ids arrays; do not invent sources. Acknowledge contradicting/missing evidence. "
        f"Research question: {protocol['research_question']}.\nEvidence: {compact}\nRAG: {rag_hits[:6]}",
        obj({"overview":S,"limitations":S,
             "themes":{"type":"array","items":obj({"name":S,"summary":S,"paper_ids":A})}}))
    for theme in result.get("themes", []):
        theme["paper_ids"] = [x for x in theme.get("paper_ids",[]) if x in valid_ids]
    return result


def prisma_counts(papers: list[dict], search_events: list[dict],
                  title_screen: list[dict], full_screen: list[dict]) -> dict:
    raw = sum(int(e.get("records",0)) for e in search_events if e.get("status")=="ok")
    dedup_info = next((e for e in search_events if e.get("source")=="deduplication"),{})
    included_title = [d for d in title_screen if d["decision"] in ("include","uncertain")]
    full_included = [d for d in full_screen if d["decision"]=="include"]
    missing = [d for d in full_screen if d["decision"]=="not_assessed_missing_fulltext"]
    excluded_full = [d for d in full_screen if d["decision"]=="exclude"]
    unresolved = [d for d in full_screen if d["decision"]=="uncertain"]
    return {"records_identified":raw,"duplicates_removed":dedup_info.get("duplicates",0),
            "unique_records_before_limit":dedup_info.get("unique_before_limit",len(papers)),
            "not_screened_due_to_limit":dedup_info.get("not_screened_due_to_limit",0),
            "records_title_screened":len(title_screen),
            "records_title_excluded":sum(d["decision"]=="exclude" for d in title_screen),
            "reports_sought_for_retrieval":len(included_title),
            "reports_not_retrieved":len(missing),
            "reports_assessed_for_eligibility":len(full_screen)-len(missing),
            "reports_excluded_at_fulltext":len(excluded_full),
            "fulltext_unresolved":len(unresolved),
            "studies_included":len(full_included),
            "note":"PRISMA-style accounting only; record eligibility is AI-assisted and requires human verification."}


def critic(state: dict) -> dict:
    papers = {p["id"]:p for p in state["papers"]}
    included = {d["paper_id"] for d in state["fulltext_screen"] if d["decision"]=="include"}
    extracted = {e["paper_id"] for e in state["extractions"]}
    checks = {
        "protocol_present":bool(state.get("protocol",{}).get("research_question")),
        "search_logged":bool(state.get("search_events")),
        "title_screen_complete":len(state["title_screen"])==len(papers),
        "extractions_match_included":included==extracted,
        "evidence_quotes_verbatim":all(e.get("evidence_supported",False) for e in state["extractions"]),
        "prisma_screened_consistent":state["prisma"]["records_title_screened"]==len(papers),
        "prisma_fulltext_consistent":state["prisma"]["reports_sought_for_retrieval"]==len(state["fulltext_screen"]),
        "all_themes_cite_included":all(set(t.get("paper_ids",[])).issubset(included)
                                      for t in state["synthesis"].get("themes",[]))
    }
    caveats = []
    if state["mode"]=="demo":
        caveats.append("SYNTHETIC FIXTURES ONLY; no actual scientific articles, Gemini, or academic APIs were used.")
    failed = [e for e in state["search_events"] if e.get("status")=="failed"]
    if failed:
        caveats.append(f"{len(failed)} search source calls failed; coverage incomplete.")
    if state["prisma"]["reports_not_retrieved"]:
        caveats.append("Some full texts unavailable; they were NOT considered included full-text studies.")
    if state["prisma"]["fulltext_unresolved"]:
        caveats.append("Full-text screening disagreements are unresolved; human review required.")
    if not checks["evidence_quotes_verbatim"]:
        caveats.append("Some extracted quotations are not verbatim; manual validation required.")
    if not all(checks.values()):
        caveats.append("Automated QA checks failed; inspect workflow before presenting results.")
    caveats.append("Automated QA and generic appraisal do NOT establish scientific validity or PRISMA compliance.")
    return {"checks":checks,"passed":sum(checks.values()),"total":len(checks),"caveats":caveats,
            "needs_human_validation":True}
