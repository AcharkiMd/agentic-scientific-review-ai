# Verification report (generated November 15, 2026)

**University:** Université Abdelmalek Essaâdi  
**Faculty:** Faculté des Sciences et Techniques de Tanger (FSTT)  
**Project repository:** https://github.com/AcharkiMd/agentic-scientific-review-ai

## Executed checks

**Runtime:** Python 3.13.5, Linux sandbox, no live third-party API credentials or internet connectivity to install missing packages.

| Verification | Outcome | Notes |
|---|---|---|
| Automated regression tests | **37 passed** | `PYTHONPATH=src python -m pytest -q` |
| Statement coverage | **79%** | `PYTHONPATH=src python -m pytest --cov=reviewai --cov-report=term-missing -q` |
| Python syntax compilation | **Passed** | `python -m compileall -q src app.py tests` |
| Synthetic end-to-end workflow | **Passed** | Explicit sequential fallback; fixture data only, no Gemini |
| SQLite persistence and human approval | **Passed** | Versioning, events, override authorization |
| Mocked scholarly source parsers | **Passed** | OpenAlex JSON, arXiv Atom XML and source-failure case |
| PDF parsing | **Passed** | In-memory synthetic PDF generated with PyMuPDF |
| Hybrid index persistence / retrieval | **Passed** | BM25 + deterministic hashing vectors, **not** semantic embeddings |
| Report/CSV/BibTeX/flow outputs | **Passed** | Files generated and asserted |
| Human gold-standard CSV metrics | **Passed** | Mechanics verified against handcrafted labels |
| Actual LangGraph execution | **Not executed** | `langgraph` not installed and package index inaccessible |
| Live Gemini SDK content/embedding calls | **Not executed** | `google-genai` unavailable and no credentials supplied |
| Live OpenAlex/arXiv/API access | **Not executed** | Network access unavailable in execution container |
| Streamlit UI rendering and clicking | **Not executed** | `streamlit` unavailable in execution container; syntax compiled |
| Live remote PDF fetch | **Not executed** | No network; safe URL handling and PDF parsing unit-tested |
| Scientific validity on real publications | **Not evaluated** | Needs expert baseline and human review |
| Manual-vs-automated time savings | **Not evaluated** | No measured manual baseline was supplied |
| PRISMA 2020 checklist compliance | **Not certified** | PRISMA-style flow counts only |

## Synthetic fixture results (not scientific evidence)

- Seven *fabricated* records retrieved; one duplicate removed.
- Six independent title/abstract pairs assessed with deterministic fixture rules.
- Four reports sought for full text; one full text deliberately unavailable; three included.
- Test-fixture screening precision, recall and F1: 1.0 each (hand-authored easy examples, **not** independent accuracy).
- Automated consistency checks: 8/8 passed.
- Embedded caution: synthetic study records, synthetic evidence and synthetic numerical findings must not be cited in any scientific manuscript.

## Remaining acceptance checks to run locally

1. Install all dependencies with `pip install -e ".[test]"` on an internet-connected machine.
2. Run `python -m pytest -q`; confirm **LangGraph** backend is selected when installed.
3. Start Streamlit and click through protocol approval/overrides and export.
4. Configure a valid Gemini key and run one live review.
5. Inspect OpenAlex/arXiv coverage, DOI/title deduplication and accessible real PDFs.
6. Verify every inclusion, extraction and narrative citation against actual papers.
7. Produce independent human adjudicated screening labels (`human_gold_template.csv`) and evaluate F1/kappa.
8. Record comparable manual-review work before reporting time savings.
9. Capture a video no longer than three minutes.

## Integrity statement

All metrics above refer to the available **offline tests**. Results have not been extrapolated to live Gemini accuracy, web-source availability, deployed UI behavior or scientific validity.
