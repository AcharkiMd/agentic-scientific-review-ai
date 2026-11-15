"""Academic connectors, audit-friendly retrieval, and conservative deduplication."""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote
import requests
from defusedxml import ElementTree as ET


def reconstruct_abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    indexed = [(int(pos), word) for word, positions in inverted_index.items() for pos in positions]
    if not indexed:
        return ""
    max_pos = max(x[0] for x in indexed)
    if max_pos > 10000:
        return ""  # Prevent a malformed API response from allocating enormous arrays.
    words = [""] * (max_pos + 1)
    for pos,word in indexed:
        words[pos] = word
    return " ".join(words).strip()


def clean_doi(doi: str | None) -> str:
    value = (doi or "").strip().lower()
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", value).strip()


def normalize_title(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD",title).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_title.lower()).strip()


def normalize_paper(paper: dict) -> dict:
    p = dict(paper)
    p["id"] = str(p.get("id") or p.get("doi") or p.get("title", "missing-id"))
    p["doi"] = clean_doi(p.get("doi"))
    p["title"] = (p.get("title") or "").strip()
    p["abstract"] = (p.get("abstract") or "").strip()
    p["authors"] = list(p.get("authors") or [])
    p["year"] = p.get("year")
    p["url"] = p.get("url") or ""
    p["pdf_url"] = p.get("pdf_url") or ""
    p["full_text"] = p.get("full_text") or ""
    p["fulltext_status"] = "available" if p["full_text"] else "not_retrieved"
    p["sources"] = list(p.get("sources") or [p.get("source", "unknown")])
    p.pop("gold_label", None)  # The benchmark label must not leak into screening.
    return p


def deduplicate(papers: list[dict]) -> tuple[list[dict], int]:
    """Prefer DOI; fallback to normalized title+year, retaining source provenance."""
    unique: dict[tuple, dict] = {}
    duplicates = 0
    for raw in papers:
        p = normalize_paper(raw)
        doi = p["doi"]
        key = ("doi", doi) if doi else ("title_year", normalize_title(p["title"]), p["year"])
        if key in unique:
            duplicates += 1
            prior = unique[key]
            prior["sources"] = sorted(set(prior["sources"] + p["sources"]))
            for field in ("abstract", "full_text", "pdf_url"):
                if len(str(p.get(field) or "")) > len(str(prior.get(field) or "")):
                    prior[field] = p[field]
            prior["fulltext_status"] = "available" if prior.get("full_text") else "not_retrieved"
        else:
            unique[key] = p
    return list(unique.values()), duplicates


class AcademicSources:
    def __init__(self, timeout: int = 20, openalex_key: str = "", openalex_email: str = "", session=None):
        self.timeout = timeout
        self.key = openalex_key
        self.email = openalex_email
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "AgenticReviewAI/0.1 (academic research prototype)"})

    def openalex(self, query: str, limit: int = 10, year_start: int | None = None) -> list[dict]:
        params: dict[str, Any] = {"search": query, "per_page": min(limit,100)}
        if self.key:
            params["api_key"] = self.key
        if self.email:
            params["mailto"] = self.email
        if year_start:
            params["filter"] = f"from_publication_date:{year_start}-01-01"
        resp = self.session.get("https://api.openalex.org/works", params=params, timeout=self.timeout)
        resp.raise_for_status()
        papers = []
        for obj in resp.json().get("results", []):
            location = obj.get("best_oa_location") or obj.get("primary_location") or {}
            authors = [a.get("author", {}).get("display_name", "")
                       for a in obj.get("authorships",[])][:12]
            papers.append({
                "id": obj.get("id", ""),
                "doi": obj.get("doi", ""),
                "title": obj.get("title") or obj.get("display_name", ""),
                "abstract": reconstruct_abstract(obj.get("abstract_inverted_index")),
                "authors": [a for a in authors if a],
                "year": obj.get("publication_year"),
                "url": obj.get("doi") or obj.get("id", ""),
                "pdf_url": location.get("pdf_url") or "",
                "source": "OpenAlex",
                "full_text": "",
            })
        return papers

    def arxiv(self, query: str, limit: int = 10) -> list[dict]:
        resp = self.session.get("https://export.arxiv.org/api/query",
                                params={"search_query": " AND ".join(
                                    "all:"+term for term in re.findall(r"[A-Za-z0-9_-]+",query)[:7]
                                    if term.upper() not in {"AND","OR","NOT"}) or "all:"+query,
                                        "start": 0, "max_results": min(limit, 100)},
                                timeout=self.timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("a:entry", ns):
            title = " ".join((entry.findtext("a:title", default="",namespaces=ns)).split())
            if not title:
                continue
            uri = entry.findtext("a:id",default="", namespaces=ns)
            pdf_links = [l.attrib.get("href","") for l in entry.findall("a:link",ns)
                         if l.attrib.get("title") == "pdf" or l.attrib.get("type") == "application/pdf"]
            authors = [x.findtext("a:name", default="",namespaces=ns)
                       for x in entry.findall("a:author",ns)]
            published = entry.findtext("a:published",default="",namespaces=ns)
            papers.append({"id":uri,"doi":"","title":title,
                           "abstract":" ".join(entry.findtext("a:summary",default="",namespaces=ns).split()),
                           "authors":authors, "year":int(published[:4]) if published[:4].isdigit() else None,
                           "url":uri,"pdf_url":pdf_links[0] if pdf_links else "",
                           "source":"arXiv", "full_text":""})
        return papers

    def search(self, queries: list[str], max_papers: int = 12, year_start: int | None = None) -> tuple[list[dict], list[dict]]:
        rows = []
        events = []
        per_call = max(2, min(20, (max_papers + len(queries) * 2 - 1) // max(1,len(queries) * 2)))
        # Search all sources even if one fails; do not misreport partial coverage as complete.
        for query in queries:
            for name, call in (("OpenAlex", lambda: self.openalex(query, per_call, year_start)),
                               ("arXiv", lambda: self.arxiv(query, per_call))):
                try:
                    result = call()
                    rows.extend(result)
                    events.append({"source":name,"query":query,"records":len(result),"status":"ok"})
                except (requests.RequestException, ET.ParseError, ValueError, KeyError) as exc:
                    events.append({"source":name,"query":query,"records":0,"status":"failed",
                                   "error":str(exc)[:300]})
        if not any(e["status"] == "ok" for e in events):
            raise RuntimeError("All academic-source requests failed. Inspect search events or network/API access.")
        unique, duplicates = deduplicate(rows)
        # Count/record all retrieved results before applying cap to make PRISMA auditable.
        events.append({"source":"deduplication","duplicates":duplicates,
                       "unique_before_limit":len(unique), "max_papers":max_papers,
                       "not_screened_due_to_limit":max(0,len(unique)-max_papers)})
        return unique[:max_papers], events


def fixture_papers(root: Path) -> tuple[list[dict],list[dict]]:
    fixture = json.loads((root / "fixtures" / "demo_papers.json").read_text(encoding="utf-8"))
    raw = fixture["papers"]
    unique, count = deduplicate(raw)
    # Explicit provenance labels; synthetic records must never be confused with real studies.
    events = [{"source":"synthetic_fixture","query":"example topic","records":len(raw),"status":"ok"},
              {"source":"deduplication","duplicates":count,"unique_before_limit":len(unique),
               "max_papers":len(unique),"not_screened_due_to_limit":0}]
    return unique, events
