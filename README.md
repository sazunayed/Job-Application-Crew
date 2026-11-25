# AI Job Application System (CrewAI + Groq)

Multi-agent system that researches a job, analyzes you, tailors and fact-checks your resume, writes a cover letter and prepares interview material.

## Structure
```
job-application-crew/
├── backend/
│   ├── app.py        FastAPI server (API + serves frontend)
│   ├── crew.py       Pipeline: scrape -> Crew kickoff -> read outputs
│   ├── agents.py     7 CrewAI agents + Groq LLM
│   ├── tasks.py      7 sequential tasks + progress step labels
│   ├── exporter.py   Markdown -> PDF / DOCX
│   ├── scrapers.py   Job page scraper + GitHub API
│   ├── config.py
│   └── outputs/      Generated markdown files
├── frontend/         index.html, style.css, script.js
├── run.py
├── requirements.txt
└── .env.example
```

## Skill gaps + learning links
A 5th agent (Skill Gap Advisor) compares the job with your profile and lists missing skills.
`backend/resources.py` attaches links (official docs map, YouTube, freeCodeCamp, Coursera, GitHub).
Links are generated in code, not by the LLM, so they never 404. Extend `OFFICIAL_DOCS` to add more.

## New: cover letter, fact check, PDF/Word, live progress
- **Cover letter agent** writes a 250-350 word letter from the fact-checked resume.
- **Fact-check reviewer agent** audits the draft resume against your real data (resume, write-up, GitHub) and removes or fixes unsupported claims. The result is shown in a **Fact check** tab; the interview prep and cover letter are built from the corrected resume.
- **PDF / Word export** for every document (`POST /api/export`, uses ReportLab + python-docx, no system libraries needed).
- **Live progress** over Server-Sent Events (`POST /api/generate/stream`): the loading screen ticks off each agent as it finishes.

## Resume upload
Users can upload an existing resume (PDF, DOCX, TXT, MD up to 5 MB). `backend/resume_parser.py` extracts the text and
the agents use it as the source of truth for experience, education and achievements. The write-up becomes optional.

## Setup
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # add your GROQ_API_KEY
python run.py
```
Open http://127.0.0.1:8000

## Notes
- Python 3.10–3.13 recommended for CrewAI.
- Change model via `GROQ_MODEL` in `.env` (e.g. `groq/llama-3.1-8b-instant` for higher free-tier limits).
- If you hit Groq rate limits, retry after a minute or use a smaller model.
- Some job sites (LinkedIn etc.) block scraping; paste a company careers page URL instead.

## Documentation
Full guides are in the [`docs/`](docs/README.md) folder:
[Getting Started](docs/01-getting-started.md) · [User Guide](docs/02-user-guide.md) · [Architecture](docs/03-architecture.md) · [Customization](docs/04-customization.md) · [Troubleshooting](docs/05-troubleshooting.md)
