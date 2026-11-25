"""Convert the Markdown that the agents write into PDF and DOCX files.

Both formats share one tiny Markdown parser (headings, bullets, numbered lists, tables,
bold / italic / code / links) so the two exports look consistent. No system libraries are
needed: PDF uses ReportLab and DOCX uses python-docx (both pure-Python installs).
"""
import io
import re
from xml.sax.saxutils import escape

# --------------------------------------------------------------------------- parsing

_INLINE = re.compile(
    r"\*\*(?P<b>.+?)\*\*"
    r"|\*(?P<i>[^*\s][^*]*?)\*"
    r"|`(?P<c>[^`]+)`"
    r"|\[(?P<lt>[^\]]+)\]\((?P<lu>[^)\s]+)\)"
)


def parse_inline(text: str) -> list[dict]:
    """Split a line into styled spans: {text, bold, italic, code, url}."""
    spans, pos = [], 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            spans.append({"text": text[pos:m.start()]})
        if m.group("b") is not None:
            spans.append({"text": m.group("b"), "bold": True})
        elif m.group("i") is not None:
            spans.append({"text": m.group("i"), "italic": True})
        elif m.group("c") is not None:
            spans.append({"text": m.group("c"), "code": True})
        else:
            spans.append({"text": m.group("lt"), "url": m.group("lu")})
        pos = m.end()
    if pos < len(text):
        spans.append({"text": text[pos:]})
    return spans


def strip_fences(md: str) -> str:
    """Remove a ```markdown fence that models sometimes wrap around the whole answer."""
    md = md.strip()
    m = re.match(r"^```[a-zA-Z]*\n(.*?)\n```$", md, re.DOTALL)
    return m.group(1).strip() if m else md


def parse_blocks(md: str) -> list[dict]:
    """Turn Markdown into a flat list of blocks: heading, para, bullet, number, hr."""
    blocks = []
    for raw in strip_fences(md).splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if m := re.match(r"^(#{1,6})\s+(.*)$", line):
            blocks.append({"type": "heading", "level": min(len(m.group(1)), 3), "text": m.group(2).strip()})
        elif re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", line):
            blocks.append({"type": "hr"})
        elif m := re.match(r"^(\s*)[-*+•]\s+(.*)$", line):
            blocks.append({"type": "bullet", "level": min(len(m.group(1)) // 2, 2), "text": m.group(2).strip()})
        elif m := re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", line):
            blocks.append({"type": "number", "level": min(len(m.group(1)) // 2, 2), "n": m.group(2), "text": m.group(3).strip()})
        elif line.lstrip().startswith("|"):
            if re.match(r"^\s*\|?[\s:|-]+\|?\s*$", line):  # table separator row
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            blocks.append({"type": "para", "text": "  |  ".join(c for c in cells if c)})
        elif m := re.match(r"^>\s?(.*)$", line):
            blocks.append({"type": "para", "text": m.group(1)})
        else:
            blocks.append({"type": "para", "text": line.strip()})
    return blocks


# --------------------------------------------------------------------------- PDF

def _pdf_safe(text: str) -> str:
    # ReportLab's built-in fonts are WinAnsi (cp1252): keep what fits, replace the rest.
    return text.encode("cp1252", "replace").decode("cp1252")


def _spans_to_xml(spans: list[dict]) -> str:
    out = []
    for s in spans:
        t = escape(_pdf_safe(s["text"]))
        if s.get("code"):
            t = f'<font face="Courier">{t}</font>'
        if s.get("bold"):
            t = f"<b>{t}</b>"
        if s.get("italic"):
            t = f"<i>{t}</i>"
        if s.get("url"):
            t = f'<a href="{escape(s["url"], {chr(34): "&quot;"})}" color="#5b3fd0">{t}</a>'
        out.append(t)
    return "".join(out)


def markdown_to_pdf(md: str, title: str = "Document") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

    base = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=13.5, alignment=TA_LEFT,
                          textColor=colors.HexColor("#1f2937"), spaceAfter=3)
    styles = {
        1: ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22, spaceAfter=6),
        2: ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                          spaceBefore=9, spaceAfter=3, textColor=colors.HexColor("#111827")),
        3: ParagraphStyle("h3", parent=base, fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=5),
    }

    story = []
    for b in parse_blocks(md):
        t = b["type"]
        if t == "heading":
            story.append(Paragraph(_spans_to_xml(parse_inline(b["text"])), styles[b["level"]]))
            if b["level"] == 2:
                story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#d1d5db"),
                                        spaceBefore=0, spaceAfter=4))
        elif t == "hr":
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#d1d5db"),
                                    spaceBefore=4, spaceAfter=6))
        elif t in ("bullet", "number"):
            indent = 12 + 12 * b["level"]
            st = ParagraphStyle("li", parent=base, leftIndent=indent + 8, bulletIndent=indent - 2, spaceAfter=2)
            bullet = "•" if t == "bullet" else f'{b["n"]}.'
            story.append(Paragraph(_spans_to_xml(parse_inline(b["text"])), st, bulletText=bullet))
        else:
            story.append(Paragraph(_spans_to_xml(parse_inline(b["text"])), base))
    if not story:
        story.append(Spacer(1, 1))

    buf = io.BytesIO()
    SimpleDocTemplate(
        buf, pagesize=A4, title=_pdf_safe(title), author="JobCrew",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    ).build(story)
    return buf.getvalue()


# --------------------------------------------------------------------------- DOCX

def _add_hyperlink(paragraph, url: str, text: str, bold=False, italic=False):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                          is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "5B3FD0")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(color)
    rpr.append(underline)
    if bold:
        rpr.append(OxmlElement("w:b"))
    if italic:
        rpr.append(OxmlElement("w:i"))
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def _docx_runs(paragraph, text: str):
    from docx.shared import Pt

    for s in parse_inline(text):
        if s.get("url"):
            _add_hyperlink(paragraph, s["url"], s["text"], s.get("bold", False), s.get("italic", False))
            continue
        run = paragraph.add_run(s["text"])
        run.bold = s.get("bold") or None
        run.italic = s.get("italic") or None
        if s.get("code"):
            run.font.name = "Courier New"
            run.font.size = Pt(9.5)


def markdown_to_docx(md: str, title: str = "Document") -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    doc.core_properties.title = title
    doc.core_properties.author = "JobCrew"
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Inches(0.8)
        sec.top_margin = sec.bottom_margin = Inches(0.7)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(3)
    for lvl, size in ((1, 20), (2, 13), (3, 11.5)):
        st = doc.styles[f"Heading {lvl}"]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0x11, 0x18, 0x27)
        st.paragraph_format.space_before = Pt(10 if lvl > 1 else 0)
        st.paragraph_format.space_after = Pt(3)

    for b in parse_blocks(md):
        t = b["type"]
        if t == "heading":
            p = doc.add_heading(level=b["level"])
            _docx_runs(p, b["text"])
        elif t == "hr":
            doc.add_paragraph("_" * 70).runs[0].font.color.rgb = RGBColor(0xD1, 0xD5, 0xDB)
        elif t == "bullet":
            style = "List Bullet" if b["level"] == 0 else f"List Bullet {min(b['level'] + 1, 3)}"
            p = doc.add_paragraph(style=style)
            _docx_runs(p, b["text"])
            p.paragraph_format.space_after = Pt(2)
        elif t == "number":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25 + 0.25 * b["level"])
            p.paragraph_format.first_line_indent = Inches(-0.2)
            p.add_run(f'{b["n"]}. ')
            _docx_runs(p, b["text"])
        else:
            _docx_runs(doc.add_paragraph(), b["text"])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
