"""Export Agent 05 Markdown docs to simple review PDFs.

This mirrors the Agent 04 PDF pattern and uses ReportLab directly so exports
are repeatable in local/offline environments.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
DOCS = ("AGENT_SPEC.md", "DESIGN.md")


def _register_font() -> tuple[str, str]:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    bold_candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]

    for regular_path, bold_path in zip(candidates, bold_candidates, strict=False):
        if regular_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont("Agent05Regular", str(regular_path)))
            pdfmetrics.registerFont(TTFont("Agent05Bold", str(bold_path)))
            return "Agent05Regular", "Agent05Bold"

    return "Helvetica", "Helvetica-Bold"


def _styles() -> dict[str, ParagraphStyle]:
    regular_font, bold_font = _register_font()
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "Agent05Title",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17324D"),
            spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "Agent05H1",
            parent=base["Heading1"],
            fontName=bold_font,
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#17324D"),
            spaceBefore=12,
            spaceAfter=7,
        ),
        "h2": ParagraphStyle(
            "Agent05H2",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#2F5E41"),
            spaceBefore=9,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Agent05Body",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=9.5,
            leading=13.2,
            spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "Agent05Bullet",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=9.2,
            leading=12.7,
            leftIndent=16,
            firstLineIndent=-8,
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "Agent05Code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.8,
            leading=9.6,
            textColor=colors.HexColor("#263238"),
            backColor=colors.HexColor("#F4F6F7"),
            borderColor=colors.HexColor("#D9E0E5"),
            borderWidth=0.25,
            borderPadding=5,
            spaceBefore=4,
            spaceAfter=6,
        ),
    }


def _inline_markdown(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def _document_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _build_story(markdown_text: str, file_name: str) -> list:
    styles = _styles()
    story: list = [
        Paragraph(_inline_markdown(_document_title(markdown_text, file_name)), styles["title"])
    ]
    in_code = False
    code_lines: list[str] = []

    def flush_code() -> None:
        nonlocal code_lines
        if code_lines:
            story.append(Preformatted("\n".join(code_lines), styles["code"], maxLineLength=96))
            code_lines = []

    for raw_line in markdown_text.splitlines()[1:]:
        line = raw_line.rstrip()

        if line.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            story.append(Spacer(1, 0.06 * inch))
            continue

        if line.startswith("# "):
            story.append(PageBreak())
            story.append(Paragraph(_inline_markdown(line[2:].strip()), styles["h1"]))
            continue

        if line.startswith("## "):
            story.append(Paragraph(_inline_markdown(line[3:].strip()), styles["h1"]))
            continue

        if line.startswith("### "):
            story.append(Paragraph(_inline_markdown(line[4:].strip()), styles["h2"]))
            continue

        if line.startswith("- "):
            story.append(Paragraph("- " + _inline_markdown(line[2:].strip()), styles["bullet"]))
            continue

        if re.match(r"^\d+\. ", line):
            story.append(Paragraph(_inline_markdown(line), styles["bullet"]))
            continue

        if line.startswith("|"):
            story.append(Preformatted(line, styles["code"], maxLineLength=96))
            continue

        story.append(Paragraph(_inline_markdown(line), styles["body"]))

    flush_code()
    return story


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#5D6D7E"))
    canvas.drawString(0.72 * inch, 0.45 * inch, "Agent 05 Editorial Planning")
    canvas.drawRightString(7.78 * inch, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def export_doc(markdown_path: Path) -> Path:
    markdown_text = markdown_path.read_text(encoding="utf-8")
    pdf_path = markdown_path.with_suffix(".pdf")
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=_document_title(markdown_text, markdown_path.stem),
        author="Agent Platform",
    )
    doc.build(_build_story(markdown_text, markdown_path.name), onFirstPage=_footer, onLaterPages=_footer)

    reader = PdfReader(str(pdf_path))
    if len(reader.pages) == 0:
        raise RuntimeError(f"{pdf_path} was generated with zero pages")
    return pdf_path


def main() -> None:
    for doc_name in DOCS:
        pdf_path = export_doc(ROOT / doc_name)
        print(f"exported {pdf_path} ({len(PdfReader(str(pdf_path)).pages)} pages)")


if __name__ == "__main__":
    main()

