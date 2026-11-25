# 3. Architecture

## Flow
```
Browser (HTML/CSS/JS)
   |  POST /api/generate/stream {job_url, github_url, writeup, resume?}
   |  <- Server-Sent Events: plan, step (active/done) ..., result | error
   v
FastAPI (backend/app.py)  -- worker thread -> queue -> SSE stream
   v
run_pipeline (backend/crew.py)
   |-- scrape_job_posting()    -> job text      (scrapers.py)
   |-- fetch_github_profile()  -> GitHub summary (scrapers.py)
   v
CrewAI Crew (Process.sequential)
   1. Job Researcher      -> job_insights
   2. Profile Analyzer    -> candidate_profile
   3. Resume Strategist   -> draft_resume          (context: 1 + 2)
   4. Fact-Check Reviewer -> fact_check            (context: 2 + 3; also sees your resume + write-up)
        answer = VERDICT line + report + "---RESUME---" + corrected resume
        crew.py splits it: report -> Fact check tab, corrected resume -> tailored_resume
   5. Interview Preparer  -> interview_materials   (context: 1 + 4)
   6. Cover Letter Writer -> cover_letter          (context: 1 + 2 + 4)
   7. Skill Gap Advisor   -> skill_gaps + MATCH_SCORE (context: 1 + 2)
   v
JSON {files{...}, resume_verdict, skill_gaps, match_score}
   v
Browser renders markdown in tabs; PDF/Word via POST /api/export
```

## Files
| Path | Responsibility |
|------|---------------|
| `backend/app.py` | API routes, serves the frontend |
| `backend/crew.py` | Orchestrates scraping + crew run, emits progress events, splits the fact-check answer |
| `backend/agents.py` | Defines the 7 agents and the Groq LLM |
| `backend/tasks.py` | Task prompts, task dependencies (`context`), progress step labels |
| `backend/exporter.py` | Markdown to PDF (ReportLab) and DOCX (python-docx) |
| `backend/scrapers.py` | Job page scraping, GitHub API |
| `backend/config.py` | Environment variables, paths, size limits |
| `frontend/` | UI: form, agent progress, tabbed markdown viewer |

## Design decisions
- **Scraping is done in plain Python, not through LLM tools.** This is more reliable with Groq-hosted models and saves tokens.
- **Sequential process**: each agent builds on earlier outputs via task `context`.
- **Input size limits** (`config.py`) keep prompts within Groq's token limits.
- **Progress streaming**: the crew runs in a background thread; each finished task pushes an event onto a queue that `/api/generate/stream` forwards as Server-Sent Events. The step list is sent by the server (`STEP_LABELS` in `tasks.py`), so adding a task only needs a new label.
- **Fact check**: the reviewer returns the report and the corrected resume in one answer, split on the `---RESUME---` marker. If the model ignores the format, the unreviewed draft is shown with a warning instead of failing the run.
- **Task results are read from `task.output`, not CrewAI's `output_file`**, because newer CrewAI versions rewrite absolute output paths. A copy of every output is still saved in `backend/outputs/<run id>/` (last 10 runs kept).
- **Export is stateless**: the browser sends the Markdown it already has; nothing is stored server-side for it.

## API
`POST /api/generate/stream` (multipart form: `job_url`, `github_url`, `writeup`, optional `resume` file)
returns `text/event-stream`. Each `data:` line is JSON:
```json
{"type":"plan","steps":["Fetching job posting and GitHub data","Analyzing the job", "..."]}
{"type":"step","index":3,"status":"active"}
{"type":"step","index":3,"status":"done"}
{"type":"result","data":{"files":{"job_insights":"..","candidate_profile":"..","tailored_resume":"..",
  "fact_check":"..","cover_letter":"..","interview_materials":".."},
  "resume_verdict":"pass|corrected|unknown","skill_gaps":[],"match_score":72}}
{"type":"error","message":"..."}
```
Validation errors (e.g. no resume and a too-short write-up) return a normal `400 {"detail": "..."}` before the stream starts.

`POST /api/generate` takes the same form and returns the final `result.data` object as one JSON response (no progress).

`POST /api/export` with JSON `{"markdown": "...", "format": "pdf" | "docx", "filename": "tailored_resume"}` returns the file as a download.

`GET /api/health` returns `{"status":"ok"}`.
