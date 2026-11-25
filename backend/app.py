import json
import queue
import re
import threading
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from .config import FRONTEND_DIR
from .crew import run_pipeline
from .exporter import markdown_to_docx, markdown_to_pdf
from .resume_parser import extract_resume_text

app = FastAPI(title="AI Job Application System (CrewAI + Groq)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _read_inputs(job_url: str, job_text: str, writeup: str, resume: Optional[UploadFile]) -> tuple[str, str]:
    """Validate the form and return (writeup, resume_text). Raises HTTPException(400)."""
    if not job_url.strip() and len(job_text.strip()) < 100:
        raise HTTPException(status_code=400, detail="Add the job posting URL, or paste the job description (at least 100 characters).")
    resume_text = ""
    if resume is not None and resume.filename:
        try:
            resume_text = extract_resume_text(resume.filename, resume.file.read())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    writeup = writeup.strip()
    if len(writeup) < 20 and not resume_text:
        raise HTTPException(status_code=400, detail="Upload your resume or write at least 20 characters about yourself.")
    return writeup, resume_text


@app.post("/api/generate")
def generate(
    job_url: str = Form(""),
    github_url: str = Form(...),
    job_text: str = Form(""),
    writeup: str = Form(""),
    resume: Optional[UploadFile] = File(None),
):
    """Blocking version: returns the finished package as one JSON response."""
    writeup, resume_text = _read_inputs(job_url, job_text, writeup, resume)
    try:
        return run_pipeline(job_url.strip(), github_url, writeup, resume_text, job_text=job_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/stream")
def generate_stream(
    job_url: str = Form(""),
    github_url: str = Form(...),
    job_text: str = Form(""),
    writeup: str = Form(""),
    resume: Optional[UploadFile] = File(None),
):
    """Server-Sent Events version. Streams `plan`, `step`, then `result` (or `error`) events."""
    writeup, resume_text = _read_inputs(job_url, job_text, writeup, resume)  # 400s are returned as normal JSON errors
    events: "queue.Queue[Optional[dict]]" = queue.Queue()

    def worker():
        try:
            result = run_pipeline(job_url.strip(), github_url, writeup, resume_text, on_event=events.put, job_text=job_text)
            events.put({"type": "result", "data": result})
        except Exception as e:
            events.put({"type": "error", "message": str(e)})
        finally:
            events.put(None)  # sentinel: stream finished

    threading.Thread(target=worker, daemon=True).start()

    def sse():
        while True:
            try:
                event = events.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"  # stops proxies / browsers closing an idle connection
                continue
            if event is None:
                return
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ExportRequest(BaseModel):
    markdown: str = Field(..., min_length=1, max_length=200_000)
    format: str = Field(..., pattern="^(pdf|docx)$")
    filename: str = "document"


@app.post("/api/export")
def export(req: ExportRequest):
    """Convert one of the generated Markdown documents to PDF or DOCX."""
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", req.filename).strip("._") or "document"
    try:
        if req.format == "pdf":
            body, mime = markdown_to_pdf(req.markdown, title=name), "application/pdf"
        else:
            body = markdown_to_docx(req.markdown, title=name)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")
    return Response(
        content=body,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{name}.{req.format}"'},
    )


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
