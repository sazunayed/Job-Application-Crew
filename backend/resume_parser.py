"""Extract plain text from an uploaded resume (PDF, DOCX, TXT, MD)."""
import io
import re
from pathlib import Path
from .config import MAX_RESUME_CHARS

MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def extract_resume_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise ValueError("Resume file is larger than 5 MB.")
    ext = Path(filename or "").suffix.lower()

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        text = "\n".join(parts)
    elif ext in (".txt", ".md"):
        text = data.decode("utf-8", errors="ignore")
    else:
        raise ValueError("Unsupported file type. Please upload PDF, DOCX, TXT or MD.")

    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    if not text:
        raise ValueError("Could not read any text from the resume (scanned PDF?). Try DOCX or TXT.")
    return text[:MAX_RESUME_CHARS]
