# Technical report — Agentic Scientific Review AI

**Status:** implementation prototype with automated offline verification; live LLM/web and UI execution require environment-specific validation.  
**Assignment:** Development of an Agentic AI Pipeline for Conducting Rigorous, Transparent, and Reproducible Systematic Reviews on Any Given Topic.  
**Module:** M1 — Agentic AI & Building AI Agents.

## 1. Abstract

This project implements a two-phase, human-supervised multi-agent software pipeline for structured literature reviews. LangGraph manages a series of specialized agents; Gemini supplies structured responses and semantic embeddings in live mode. OpenAlex and arXiv provide bibliographic metadata. Open-access full texts, when accessible, are parsed into bounded extracts. Hybrid dense/BM25 retrieval supplies grounded material to the synthesis agent. SQLite saves versioned run states, approvals, overrides and audit events. Outputs include protocol/search logs, title and full-text screening decisions, evidence tables, BibTeX metadata, PRISMA-style counts and an audit-ready review manuscript. An offline synthetic fixture tests the workflow without representing real academic research.

## 2. Objectives and requirements traceability

| Assignment objective | Implementation | Limitation |
|---|---|---|
| Multi-agent architecture | LangGraph prepare and complete graphs; seven functions | Real LangGraph package integration requires live-environment verification |
| Scientific corpora | OpenAlex + arXiv connectors | PubMed/Semantic Scholar not integrated; source coverage incomplete |
| Advanced RAG | Gemini embeddings, local NumPy vector index, BM25 fusion, excerpts | No cross-encoder reranker or trained semantic compression beyond truncation |
| PRISMA workflow | Protocol, search, dual simulated title/fulltext screening, data extraction, narrative synthesis, flow totals | PRISMA-style only; no completed checklist validation or genuine dual human screening |
| Quality/risk of bias | LLM generic methodological concern rating | Not a validated topic-specific risk-of-bias method |
| Quantitative synthesis | Study-level export and comparison-ready evidence table | No automatic statistical meta-analysis computation |
| Transparency | SQLite events, paper/quote provenance, saved artifacts, checksums | Audit does not prove correctness |
| Human oversight | Review before continuation, screening overrides | No post-full-text interactive adjudication loop in MVP |
| General topics | Protocol and search driven by research question | Demo fixture only supports lakehouse; live academic sources have discipline biases |

## 3. Architecture

The coordinator first generates a structured protocol; the strategy agent produces scholarly search terms. The retrieval agent queries two external services and deduplicates records. Two separately prompted reviewers classify titles/abstracts and preserve each rationale. The workflow stops for user approval and possible corrections. Approved records are retrieved as bounded PDFs when allowed, screened again, and converted into structured evidence. Only full-text-included records enter the RAG index. The synthesis agent produces evidence-based themes from extracted results and retrieved passages; the deterministic critic validates basic counts, citation IDs and verbatim evidence quotations. Reports and the SHA-256 manifest are written to a per-run directory.

Two compact LangGraph DAGs are used so that the human approval gate is an explicit application boundary. A demo-only sequential fallback makes the repository testable without installing the LangGraph package; it cannot be used for live mode.

## 4. Data design and reliability

SQLite tables: `runs` (`id`, `topic`, `mode`, `status`, `state_json`, `approved`, `version`, timestamps), `events` (stage, level, payload, time), and `overrides` (paper, decision, reason). Each agent node saves a JSON state snapshot and an audit event. This is durable state and versioning, but not full automatic resume/checkpoint replay.

For scientific reliability, full-text unavailable records are not treated as eligible full-text studies; screening conflicts do not silently become accepted; output themes cite existing included source IDs; exact quotations are checked against the extracted text. Lexical quote matching alone cannot validate that a claim follows logically from the passage; all claims require human review.

## 5. Methods

### Search and selection

OpenAlex full-text/title/abstract indexed search and arXiv Atom feeds provide candidate records. Metadata is normalized and deduplicated by DOI when present or normalized title/year otherwise. Search events retain source, query, retrieved count, and failures. Review results are bounded by the configured maximum to constrain demonstration cost, so they cannot be described as exhaustive.

### Screening

Two distinct Gemini agent prompts assess each title/abstract; disagreements are `uncertain` and require human resolution at the title-screen gate. Full-text decisions are independently generated, but unresolved conflicts are not included. Demo rules are simplistic lexical checks that are *only* adequate for fixture-control testing.

### Evidence retrieval and quality assessment

Accessible HTTPS PDFs are retrieved and parsed using PyMuPDF with size, page, and length limits. Extraction produces design, methods, findings, limitations, generic methodological concern, and a verbatim quote. The system stores a boolean source-match result for every quote. Unavailable full text is recorded, not reconstructed from metadata.

### Retrieval-augmented synthesis

Document text is chunked into overlapping passages. In live mode Gemini embedding vectors are generated, and in demo mode deterministic hashing vectors are substituted. A local vector index stores chunk metadata and vectors. At query time a weighted dense cosine plus BM25 score ranks passages, and bounded excerpts provide evidence context to Gemini for grounded narrative synthesis.

### QA and exports

The critic checks internal arithmetic, quote presence, inclusion/extraction correspondence, citations and screening completeness. Artifacts are exported as Markdown, JSON, CSV, BibTeX and SVG. A manifest contains file-level SHA-256 fingerprints. Automated checks are necessary but not sufficient for methodological validity.

## 6. Experiment and evaluation

### Offline synthetic run — strictly a software fixture

The fixture includes **7 invented source rows**, a **duplicate**, **6** unique screened records, **4** title-included records, **1** deliberately missing full text and **3** full-text-included synthetic studies. The complete pipeline ran and generated saved artifacts. Rule-based screening matched all six hand-authored fixture labels, yielding an artificial **F1 = 1.0**. This result is not generalizable and is not a real scientific screening result.

Automated regression checks were executed on the current source tree; see `docs/TEST_REPORT.md` for exact counts and testing constraints. Not performed: live Google Gemini call, deployed Streamlit UI smoke test, actual scholarly-API calls, real-PDF source fetching, scientific accuracy versus independent expert judgments, and measured manual-vs-automated time savings.

### Proposed scientific evaluation (not yet completed)

Collect a sample of real papers; establish human-adjudicated decisions without model exposure; compare precision/recall/F1 and reviewer agreement, manually verify extraction facts and source support, measure corpus coverage and compare hands-on review time using a controlled and equivalent manual process. Report confidence intervals and unresolved systematic biases where appropriate.

## 7. Strengths and limitations

The main software contributions are modularity, end-to-end control flow, evidence provenance, auditability, human approval, transparent failures and reproducible synthetic tests. The principal scientific limitations are partial corpus coverage, methodologically nonvalidated AI screening, no domain-specific risk-of-bias implementation, reduced full-text availability, simplified reranking and absence of genuine independent evaluation. The system is a **prototype** and should not be presented as having completed an unsupervised rigorous systematic review.

## 8. Individual contributions

**The team must complete and verify this section before submission.** Use `CONTRIBUTIONS.md`; enter actual individual work, ownership, tests and repository commits. Do not invent student names or claim that unperformed validation took place.

## 9. Conclusion

The prototype implements the requested major pipeline stages and supports teaching demonstrations of multi-agent workflow design, evidence tracking, hybrid RAG and critical human-in-the-loop review. Further improvements required for a robust research system include multiple academic connectors, better source coverage, specific bias-assessment frameworks, systematic manual validation, checklist-level PRISMA verification, and live deployment tests.
