# Quick start — minimum steps

## PowerShell on Windows (Python 3.12)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
reviewai demo
streamlit run app.py
```

The offline demo uses **fabricated** studies (no API key). For a live review, edit `.env`, add `GEMINI_API_KEY=...`, choose **Live** in the UI and approve the protocol/screening.

## Verify

```powershell
python -m pytest -q
python -m compileall -q src app.py
```

## Submission

Read `docs/SUBMISSION_CHECKLIST.md`, `TECHNICAL_REPORT.md`, `CONTRIBUTIONS.md`, and `DEMO_SCRIPT.md`. Upload source to your own GitHub/GitLab account and record a video <=3 minutes.

**Live Gemini and web-source integration have not been tested in the package creation environment.**
