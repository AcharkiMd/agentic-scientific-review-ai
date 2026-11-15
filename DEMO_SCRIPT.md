# Three-minute demonstration — suggested script and recording outline

**University:** Université Abdelmalek Essaâdi  
**Faculty:** Faculté des Sciences et Techniques de Tanger (FSTT)  
**Project repository:** https://github.com/AcharkiMd/agentic-scientific-review-ai

**Important:** The recorded demo must represent the application you actually ran. The synthetic offline mode must be explicitly identified as *fabricated records*; for a legitimate scientific review demonstration, use and validate a live run with real papers. Never present the offline fixture as actual research evidence.

| Time | Screen to record | Narration |
|---|---|---|
| 00:00–00:20 | Title + project diagram in README | "Our application coordinates specialist agents for a PRISMA-aligned, traceable scientific review." |
| 00:20–00:40 | Streamlit home: choose mode and enter research question | "The question controls the protocol, search terms and downstream stages. The offline demonstration uses synthetic records." |
| 00:40–01:05 | Protocol JSON, queries, search log | "The coordinator defines selection criteria and search agents retain source-specific query and result counts." |
| 01:05–01:30 | Screening dataframe with individual decisions | "Independent reviewer prompts give separate decisions; disagreements and human overrides are auditable." |
| 01:30–01:50 | Human approval checkbox; begin continuation | "The pipeline pauses for human approval before full-text analysis." |
| 01:50–02:15 | Review report and evidence table | "The synthesis uses included full-text evidence. Records with missing full text are excluded from the full-text evidence synthesis." |
| 02:15–02:35 | PRISMA counts, QA caveats, RAG/index files | "The critic checks internal consistency, quote provenance and citation IDs; these checks do not replace human scientific review." |
| 02:35–02:50 | Download ZIP artifacts, audit log, test result | "All key decisions, metrics and exports can be inspected and reproduced." |
| 02:50–03:00 | Git repository + final deliverables | "This is a supervised prototype. Real scientific validation and comprehensive coverage remain future work." |

## Recording procedure

1. Run `streamlit run app.py`, choose **Synthetic offline demo**, and generate the fixture review.
2. Pre-run the complete review before recording so you can navigate a completed run quickly.
3. Optionally demonstrate a human override in a separate preparation run.
4. Keep the edited video at or under **180 seconds**.
5. Show `python -m pytest -q` output and identify it as an **offline test suite**, not an external API or model benchmark.
6. If showing the live mode, capture real source/API results and document any failures; review sources for correctness first.

## Suggested slide caption

"Research prototype — academic retrieval and AI-generated screening require human validation. Synthetic demonstration content is not real scientific literature."
