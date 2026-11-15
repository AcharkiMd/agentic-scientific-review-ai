"""Reference-safe exports: Markdown, CSV, BibTeX, PRISMA-style SVG and manifest."""
from __future__ import annotations
import csv
import hashlib
import html
import io
import json
import re
import zipfile
from pathlib import Path
from .storage import Store


def _citation_key(p: dict) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_",p["id"])[-70:]


def _md_safe(s: str) -> str:
    return (str(s or "").replace("|","\\|").replace("\n"," ")).strip()


def bibliography(papers: list[dict], mode: str) -> str:
    lines=[]
    for p in papers:
        authors = " and ".join(p.get("authors",[]) or ["Unknown"])
        # Demo bibliographic metadata is fabricated and clearly marked.
        title=("[SYNTHETIC TEST RECORD] " if mode=="demo" else "") + p["title"]
        lines.append("@misc{"+_citation_key(p)+",\n  title = {"+title.replace("{","").replace("}","")+"},\n"
                     +"  author = {"+authors.replace("{","").replace("}","")+"},\n"
                     +"  year = {"+str(p.get("year") or "n.d.")+"},\n"
                     +"  url = {"+str(p.get("url","")).replace("{","").replace("}","")+"},\n"
                     +"  note = {"+("NOT A REAL PUBLICATION" if mode=="demo" else "Metadata retrieved from scholarly index; verify before citation")+"}\n}\n")
    return "\n".join(lines)


def make_report(s: dict) -> str:
    p=s["protocol"]
    prs=s["prisma"]
    qa=s["quality_assurance"]
    title="SYSTEMATIC REVIEW — SYNTHETIC DEMONSTRATION" if s["mode"]=="demo" else "AI-assisted systematic literature review — draft"
    out=[f"# {title}","",f"**Research question:** {p['research_question']}",
         f"**Run:** `{s['run_id']}` | **Mode:** `{s['mode']}` | **Model:** "
         + ("DEMO RULES (NO GEMINI)" if s["mode"]=="demo" else "Google Gemini"),"",
         "> **Important:** Machine-generated draft. Requires independent human methodological review. "
         +("All included papers and evidence in this demonstration are FABRICATED. " if s["mode"]=="demo" else "")
         +"This report does not establish completed PRISMA compliance.","",
         "## 1. Review protocol",f"**Objective:** {p['objective']}",
         "**Inclusion criteria:** "+"; ".join(p["inclusion_criteria"]),
         "**Exclusion criteria:** "+"; ".join(p["exclusion_criteria"]),
         f"**Sources:** {', '.join(p['databases'])}","",
         "## 2. Search strategy and reproducibility",]
    for q in s["queries"]:
        out.append(f"- `{q}`")
    out.append("**Search execution:**")
    for event in s["search_events"]:
        if event.get("source")=="deduplication":
            out.append(f"- Deduplication: {event.get('duplicates',0)} removed; "
                       f"{event.get('not_screened_due_to_limit',0)} records not screened because of sample cap")
        else:
            out.append(f"- {event['source']} | `{event.get('query','')}` | {event['status']} "
                       f"| {event.get('records',0)} records")
    out.extend(["","## 3. PRISMA-style flow counts", "", "| Stage | Count |", "|---|---:|"])
    for k,v in prs.items():
        if isinstance(v,int):
            out.append(f"| {k.replace('_',' ').capitalize()} | {v} |")
    out.extend(["", "## 4. Included-study evidence table", "",
                "| Paper ID | Study | Design | Finding (from extraction) | Quality concern | Quote verified |",
                "|---|---|---|---|---|---|"])
    for e in s["extractions"]:
        out.append("| "+" | ".join(_md_safe(x)[:350] for x in (
            e["paper_id"],e["title"],e.get("study_design",""),e.get("findings",""),
            e.get("risk_of_bias",""),"yes" if e.get("evidence_supported") else "NO"))+" |")
    if not s["extractions"]:
        out.append("No accessible full-text study passed eligibility screening.")
    out.extend(["", "## 5. Narrative synthesis","",s["synthesis"].get("overview",""),""])
    for theme in s["synthesis"].get("themes",[]):
        refs=[x for x in theme.get("paper_ids",[]) if x in {e["paper_id"] for e in s["extractions"]}]
        out.extend([f"### {theme.get('name','Theme')}",theme.get("summary",""),
                    "**Supporting study IDs:** "+(", ".join(f"[{r}]" for r in refs) if refs else "None"),""])
    out.extend(["### Limitations",s["synthesis"].get("limitations",""),"",
                "## 6. Quality assurance",f"**Automated checks:** {qa['passed']}/{qa['total']} passed",""])
    for name,value in qa["checks"].items():
        out.append(f"- {'PASS' if value else 'FAIL'} — {name}")
    for item in qa["caveats"]:
        out.append(f"- **Caveat:** {item}")
    out.extend(["", "## 7. Study references (retrieved metadata)",""])
    for paper in s["papers"]:
        if paper["id"] in {e["paper_id"] for e in s["extractions"]}:
            out.append(f"- [{paper['id']}] {', '.join(paper['authors']) or 'Unknown'} "
                       f"({paper['year'] or 'n.d.'}). *{paper['title']}*. "
                       + (f"{paper['url']}" if paper.get("url") else "[fixture record: no genuine URL]"))
    out.extend(["", "## 8. Evidence limits", "Full-text unavailable reports are not included in synthesis. "
                "AI screening is not a substitute for two independent human reviewers; "
                "automated appraisal is not a validated domain-specific risk-of-bias tool. "
                "This draft has not undergone protocol preregistration or complete PRISMA 2020 checklist verification.",""])
    return "\n".join(out)


def _csv(data: list[dict], fields: list[str]) -> str:
    out=io.StringIO()
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction="ignore")
    writer.writeheader()
    for item in data:
        row={k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in item.items()}
        writer.writerow(row)
    return out.getvalue()


def prisma_svg(p: dict) -> str:
    # Basic standalone PRISMA-style visualization. NOT the official PRISMA 2020 diagram.
    steps=[("Records identified",p["records_identified"]),
           ("Duplicates removed",p["duplicates_removed"]),
           ("Title and abstract screened",p["records_title_screened"]),
           ("Title/abstract excluded",p["records_title_excluded"]),
           ("Reports sought",p["reports_sought_for_retrieval"]),
           ("Reports not retrieved",p["reports_not_retrieved"]),
           ("Full-text assessed",p["reports_assessed_for_eligibility"]),
           ("Full-text excluded",p["reports_excluded_at_fulltext"]),
           ("Studies included",p["studies_included"]) ]
    content=['<svg xmlns="http://www.w3.org/2000/svg" width="680" height="940" viewBox="0 0 680 940">',
             '<rect width="680" height="940" fill="#ffffff"/>',
             '<text x="340" y="33" text-anchor="middle" font-size="17" font-family="sans-serif">PRISMA-style flow (prototype, not official)</text>']
    for i,(label,count) in enumerate(steps):
        y=57+i*92
        content.extend([f'<rect x="90" y="{y}" width="500" height="66" rx="9" fill="#eff6ff" stroke="#60a5fa"/>',
                        f'<text x="340" y="{y+26}" text-anchor="middle" font-size="15" font-family="sans-serif">{html.escape(label)}</text>',
                        f'<text x="340" y="{y+49}" text-anchor="middle" font-weight="bold" font-size="17" font-family="sans-serif">n = {count}</text>'])
        if i<len(steps)-1:
            content.append(f'<path d="M340 {y+66} V{y+88}" stroke="#475569" stroke-width="2" fill="none"/>')
    content.append('</svg>')
    return '\n'.join(content)


def export_run(store: Store, run_id: str) -> Path:
    state=store.get(run_id)["state"]
    if "quality_assurance" not in state:
        raise ValueError("Run is not complete; no final output to export")
    folder=store.output_dir(run_id)
    outputs={
        "systematic_review.md":make_report(state),
        "protocol.json":json.dumps(state["protocol"],ensure_ascii=False,indent=2),
        "search_log.json":json.dumps(state["search_events"],ensure_ascii=False,indent=2),
        "papers.json":json.dumps(state["papers"],ensure_ascii=False,indent=2),
        "title_screening.csv":_csv(state["title_screen"],["paper_id","decision","rationale","conflict","reviewers","human_override"]),
        "fulltext_screening.csv":_csv(state["fulltext_screen"],["paper_id","decision","rationale","conflict","reviewers"]),
        "evidence_table.csv":_csv(state["extractions"],["paper_id","title","year","study_design","methods","findings","limitations","risk_of_bias","evidence_quote","evidence_supported","source_scope"]),
        "human_gold_template.csv":_csv([{"paper_id":p["id"],"title":p["title"],"human_label":""}
                                      for p in state["papers"]], ["paper_id","title","human_label"]),
        "evidence_map.json":json.dumps({t.get("name","Unnamed theme"):t.get("paper_ids",[])
                                  for t in state["synthesis"].get("themes",[])},ensure_ascii=False,indent=2),
        "references.bib":bibliography(state["papers"],state["mode"]),
        "prisma_counts.json":json.dumps(state["prisma"],ensure_ascii=False,indent=2),
        "prisma_flow.svg":prisma_svg(state["prisma"]),
        "qa.json":json.dumps(state["quality_assurance"],ensure_ascii=False,indent=2),
        "rag_evidence.json":json.dumps(state["rag_hits"],ensure_ascii=False,indent=2),
        "audit_trail.json":json.dumps(store.events(run_id),ensure_ascii=False,indent=2),
        "state.json":json.dumps(state,ensure_ascii=False,indent=2),
    }
    for name,content in outputs.items():
        (folder/name).write_text(content,encoding="utf-8")
    manifest={"run_id":run_id,"mode":state["mode"],"runtime":state.get("runtime"),
              "files_sha256":{name:hashlib.sha256(content.encode("utf-8")).hexdigest()
                              for name,content in outputs.items()}}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return folder


def zip_outputs(folder: Path) -> bytes:
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                z.write(file,file.relative_to(folder))
    return out.getvalue()
