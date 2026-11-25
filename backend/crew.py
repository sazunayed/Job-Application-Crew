import re
import shutil
import time
import uuid
from typing import Callable, Optional

from crewai import Crew, Process
from .agents import build_agents, build_llm
from .tasks import build_tasks, STEP_LABELS, TASK_OUTPUT_NAMES
from .scrapers import scrape_job_posting, fetch_github_profile
from .resources import parse_skill_gaps, parse_match_score
from .exporter import strip_fences
from .config import OUTPUT_DIR, API_KEY, KEY_NAME, LLM_COOLDOWN_SECONDS, MIN_JOB_CHARS, MAX_JOB_CHARS

KEEP_RUNS = 10  # how many past run folders to keep in backend/outputs/
MIN_RESUME_CHARS = 200  # a "corrected" resume shorter than this is treated as a failed review


def _clean(text: str) -> str:
    """Drop <think>/<thought> reasoning blocks that some models (Qwen, DeepSeek, Gemma) include."""
    return re.sub(r"<(think|thought|thinking)>.*?</\1>", "", text or "", flags=re.DOTALL | re.IGNORECASE).strip()


def _read(path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _prune_old_runs():
    runs = sorted((d for d in OUTPUT_DIR.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)
    for d in runs[KEEP_RUNS:]:
        shutil.rmtree(d, ignore_errors=True)


def split_review(raw: str, draft: str) -> tuple[str, str, str]:
    """Split the fact-checker's answer into (verdict, report_markdown, final_resume).

    Falls back to the unreviewed draft if the model did not follow the layout, so the user
    always gets a resume and is told the review could not be applied.
    """
    raw = strip_fences(raw or "")
    parts = re.split(r"-{3}\s*RESUME\s*-{3}", raw, maxsplit=1, flags=re.IGNORECASE)
    head = parts[0]
    resume = strip_fences(parts[1]) if len(parts) == 2 else ""

    m = re.search(r"VERDICT:\s*(PASS|CORRECTED)", head, re.IGNORECASE)
    verdict = m.group(1).lower() if m else "unknown"
    report = re.sub(r"^\s*VERDICT:.*$", "", head, count=1, flags=re.IGNORECASE | re.MULTILINE).strip()

    if len(resume) < MIN_RESUME_CHARS:
        note = ("_The reviewer did not return a usable corrected resume, so the **unreviewed draft** is shown. "
                "Check it carefully before sending, or run again._")
        report = f"{note}\n\n{report}" if report else note
        return "unknown", report, strip_fences(draft)
    if not report:
        report = "## Fact-check report\n- No report was returned."
    return verdict, report, resume


def get_job_text(job_url: str, pasted: str) -> str:
    """Prefer text the user pasted; otherwise scrape the URL and fail early if it gave nothing useful."""
    pasted = (pasted or "").strip()
    if len(pasted) >= 100:
        return pasted[:MAX_JOB_CHARS]
    text = scrape_job_posting(job_url) if job_url else ""
    if text.startswith("[") or len(text) < MIN_JOB_CHARS:
        reason = text if text.startswith("[") else "the page returned almost no text"
        raise RuntimeError(
            "Could not read the job posting from that link (" + reason.strip("[]") + "). Many job sites "
            "(LinkedIn, Indeed, and pages built with JavaScript) block automated reading. Copy the job "
            "description from your browser and paste it into the 'Job description' box instead."
        )
    return text


def run_pipeline(
    job_url: str,
    github_url: str,
    writeup: str,
    resume_text: str = "",
    on_event: Optional[Callable[[dict], None]] = None,
    job_text: str = "",
) -> dict:
    """Run the whole crew. `on_event` receives progress dicts:
    {"type": "plan", "steps": [...]} and {"type": "step", "index": i, "status": "active" | "done"}.
    """
    if not API_KEY:
        raise RuntimeError(f"{KEY_NAME} is missing. Add it to your .env file.")

    def emit(event: dict):
        if on_event:
            try:
                on_event(event)
            except Exception:  # progress reporting must never break the run
                pass

    run_dir = OUTPUT_DIR / uuid.uuid4().hex[:12]  # own folder per run, so parallel runs can't collide
    run_dir.mkdir(parents=True, exist_ok=True)
    _prune_old_runs()

    emit({"type": "plan", "steps": STEP_LABELS})
    emit({"type": "step", "index": 0, "status": "active"})
    inputs = {
        "job_text": get_job_text(job_url, job_text),
        "github_data": fetch_github_profile(github_url),
        "writeup": writeup or "(not provided)",
        "resume_text": resume_text or "(no existing resume uploaded)",
    }
    emit({"type": "step", "index": 0, "status": "done"})

    def on_task_done(i: int):  # task i is STEP_LABELS[i + 1]
        emit({"type": "step", "index": i + 1, "status": "done"})
        if LLM_COOLDOWN_SECONDS and i + 2 < len(STEP_LABELS):
            time.sleep(LLM_COOLDOWN_SECONDS)  # let a small per-minute token window recover
        if i + 2 < len(STEP_LABELS):
            emit({"type": "step", "index": i + 2, "status": "active"})

    emit({"type": "step", "index": 1, "status": "active"})
    agents = build_agents(build_llm())
    tasks = build_tasks(agents, on_task_done)
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )
    crew.kickoff(inputs=inputs)

    # Read each task's answer and keep a copy on disk in this run's folder.
    raw = {}
    for name, task in zip(TASK_OUTPUT_NAMES, tasks):
        raw[name] = _clean(task.output.raw if task.output else "")
        ext = "json" if name == "skill_gaps" else "md"
        (run_dir / f"{name}.{ext}").write_text(raw[name], encoding="utf-8")

    verdict, report, final_resume = split_review(raw["fact_check"], raw["draft_resume"])
    (run_dir / "tailored_resume.md").write_text(final_resume, encoding="utf-8")
    files = {
        "job_insights": raw["job_insights"],
        "candidate_profile": raw["candidate_profile"],
        "tailored_resume": final_resume,
        "fact_check": report,
        "cover_letter": strip_fences(raw["cover_letter"]),
        "interview_materials": raw["interview_materials"],
    }
    files = {k: (v.strip() or "_No output generated._") for k, v in files.items()}

    raw_gaps = raw["skill_gaps"]
    return {
        "files": files,
        "resume_verdict": verdict,  # "pass" | "corrected" | "unknown"
        "skill_gaps": parse_skill_gaps(raw_gaps),
        "match_score": parse_match_score(raw_gaps),
    }
