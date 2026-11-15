# Troubleshooting

- **`ModuleNotFoundError: langgraph` / `streamlit` / `google.genai`:** Activate your virtual environment, confirm `python --version`, run `python -m pip install -e ".[test]"` with internet access.
- **"GEMINI_API_KEY is required"**: Add `GEMINI_API_KEY` to `.env` and restart the app. The synthetic demo does not need it.
- **Gemini model not found / quota:** Check model availability for your API project; change `GEMINI_MODEL` and `GEMINI_EMBEDDING_MODEL` in `.env`. Review your account's quota/cost policy.
- **Live sources return zero papers:** Academic APIs may rate-limit requests, change schemas, or reject query syntax. Try a simpler research question and inspect the per-query search log.
- **Full-text PDFs not retrieved:** Automatic retrieval allows bounded direct HTTPS public URLs and rejects redirects/oversize/unreadable files. Missing PDFs are explicitly excluded from full-text studies.
- **Title-screening `uncertain`:** Save a human override with a reason before continuing.
- **Preparation or completion failed:** The last SQLite state snapshot is preserved. Restart with a *new* run ID; automatic failed-node replay is not implemented.
- **PowerShell denies venv activation:** Use `python.exe` from `.venv\Scripts\` directly or adjust execution policy under your organization's rules.
- **No real accuracy number appears:** Supply independent human labels using the output CSV template. The system intentionally does not invent an accuracy claim.
- **AI output unsupported or misleading:** Check the original paper, quote and table manually. Re-run with narrower criteria or exclude unreliable records.
