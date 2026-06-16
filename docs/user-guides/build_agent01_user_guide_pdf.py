"""Build the Agent 01 user guide PDF."""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


OUT_DIR = Path(__file__).resolve().parent
PDF_PATH = OUT_DIR / "agent-01-blog-writing-agent-user-guide.pdf"

BLUE = colors.HexColor("#2E74B5")
DARK_BLUE = colors.HexColor("#1F4E78")
PALE_BLUE = colors.HexColor("#E8EEF5")
PALE_GRAY = colors.HexColor("#F4F6F9")
TEXT = colors.HexColor("#222222")
MUTED = colors.HexColor("#666666")
BORDER = colors.HexColor("#C9D3E0")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "GuideTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=30,
            textColor=DARK_BLUE,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "GuideSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=MUTED,
            spaceAfter=12,
        ),
        "meta": ParagraphStyle(
            "GuideMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "GuideHeading1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=BLUE,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "GuideHeading2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=DARK_BLUE,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "GuideBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.8,
            leading=14,
            textColor=TEXT,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "GuideSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=TEXT,
        ),
        "table_header": ParagraphStyle(
            "GuideTableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=TEXT,
        ),
        "table_cell": ParagraphStyle(
            "GuideTableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=10.5,
            textColor=TEXT,
        ),
        "callout_title": ParagraphStyle(
            "GuideCalloutTitle",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=DARK_BLUE,
            spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "GuideCode",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.6,
            leading=9.5,
            textColor=colors.HexColor("#111111"),
        ),
        "footer": ParagraphStyle(
            "GuideFooter",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def heading(text: str, styles: dict[str, ParagraphStyle], level: int = 1) -> Paragraph:
    return p(text, styles["h1" if level == 1 else "h2"])


def para(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return p(text, styles["body"])


def bullets(items: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, styles["body"]), leftIndent=12) for item in items],
        bulletType="bullet",
        start="circle",
        leftIndent=18,
        bulletFontName="Helvetica",
        bulletFontSize=7,
    )


def numbers(items: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, styles["body"]), leftIndent=16) for item in items],
        bulletType="1",
        leftIndent=20,
        bulletFontName="Helvetica",
        bulletFontSize=8,
    )


def code_block(text: str, styles: dict[str, ParagraphStyle]) -> Table:
    cleaned = text.strip("\n")
    block = Preformatted(cleaned, styles["code"])
    table = Table([[block]], colWidths=[6.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F7F7")),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def callout(title: str, body: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table(
        [[p(title, styles["callout_title"])], [p(body, styles["small"])]],
        colWidths=[6.8 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_GRAY),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def info_table(
    headers: list[str],
    rows: list[list[str]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
) -> Table:
    data = [[p(h, styles["table_header"]) for h in headers]]
    data.extend([[p(cell, styles["table_cell"]) for cell in row] for row in rows])
    table = Table(data, colWidths=[width * inch for width in widths], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(doc.leftMargin, 0.55 * inch, LETTER[0] - doc.rightMargin, 0.55 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 0.35 * inch, "Agent 01 Blog Writing Agent Guide")
    canvas.drawRightString(
        LETTER[0] - doc.rightMargin,
        0.35 * inch,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=LETTER,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.75 * inch,
        title="Agent 01 Blog Writing Agent User Guide",
        author="Agents Platform",
        subject="How to use Agent 01 Blog Writing Agent",
    )

    story = [
        p("Agent 01 Blog Writing Agent", styles["title"]),
        p("User Guide for the review-ready blog package UI", styles["subtitle"]),
        p(f"Updated: {date.today().isoformat()}  |  Scope: Agent 01 v1  |  Mode: draft-only", styles["meta"]),
        callout(
            "One-line summary",
            "Agent 01 turns messy text, voice recordings, or audio-only video input into a review-ready blog package. It drafts, reviews, scores, and flags issues, but it does not publish anywhere.",
            styles,
        ),
        heading("1. What Agent 01 Is Trying To Do", styles),
        para(
            "Agent 01 is the platform's golden/reference agent. It was built first so its architecture, provider abstractions, cost controls, tests, and UI pattern can be reused by later agents.",
            styles,
        ),
        para(
            "For the user, its practical job is simple: take rough source material and produce a blog package that a human can review, edit lightly, and publish manually outside the agent.",
            styles,
        ),
        bullets(
            [
                "Input: text, voice upload, video upload, or a structured Agent 03 blog brief.",
                "Process: normalize the source, extract ideas, plan the post, draft, review, and finalize.",
                "Output: title, summary, full draft, SEO keywords, tags, meta description, quality score, notes, and cost.",
                "Boundary: v1 is draft-only. It never publishes, posts to social media, writes to a CMS, scrapes the web, or analyzes video frames.",
            ],
            styles,
        ),
        heading("2. What It Can And Cannot Do", styles),
        info_table(
            ["Can do", "Cannot do in v1"],
            [
                ["Turn messy notes into a blog draft.", "Publish the blog or write to a CMS."],
                ["Transcribe voice recordings through the configured transcription provider.", "Use autonomous web search or live scraping."],
                ["Extract audio from video and transcribe it.", "Analyze video visuals, key frames, or screen content."],
                ["Handle pasted reference material as untrusted inspiration.", "Copy or spin source/reference material."],
                ["Track per-stage cost and stop before the Rs 50 ceiling.", "Guarantee factual claims without evidence."],
            ],
            [3.4, 3.4],
            styles,
        ),
        heading("3. How The Blog Pipeline Works", styles),
        numbers(
            [
                "Intake checks the input type and rejects unsupported or empty input before expensive work.",
                "For voice, the file is transcribed. For video, audio is extracted first, then transcribed. Video visuals are ignored in v1.",
                "Normalize cleans the content and separates usable source material from commands or weak input.",
                "Extract ideas identifies the main idea, supporting points, audience, and usable angle.",
                "Plan creates title candidates, outline, tone, audience, and keywords.",
                "Draft writes the blog using the plan and source material.",
                "Review scores the draft out of 100 and flags hard-fail issues.",
                "Finalize assembles the BlogPackage with status, draft, notes, quality, and cost.",
            ],
            styles,
        ),
        heading("4. Output Statuses", styles),
        info_table(
            ["Status", "Meaning", "What to do"],
            [
                ["pass", "Quality score is at least 80 and no hard-fail condition triggered.", "Review the draft, edit lightly, and publish manually outside the agent."],
                ["needs_human", "Input is too thin, unsafe, unsupported, or the review found a problem that needs a person.", "Add better source material or fix the issue noted in the result."],
                ["stopped_cost_ceiling", "The run stopped to protect the Rs 50 budget ceiling.", "Use shorter input or retry later with a cheaper path."],
                ["error", "A provider, config, file, or graph issue stopped the run.", "Check the terminal running uvicorn and verify GCP/env setup."],
            ],
            [1.25, 2.9, 2.65],
            styles,
        ),
        PageBreak(),
        heading("5. How To Start The UI In Live GCP Mode", styles),
        para("Open PowerShell and run these from the repository root:", styles),
        code_block(
            r'''
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"

$repo = (Get-Location).Path
$env:BLOG_UI_PROVIDER = "gcp"
$env:VERTEX_AI_PROJECT = "agents-platform-1212"
$env:GCS_BLOG_BUCKET = "agents-platform-1212-agents-platform-stt-smoke"
$env:PYTHONPATH = "$repo\packages;$repo\agents\agent-01-blog-writer"

Set-Location "$repo\apps\blog-ui"
& "$repo\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8001
''',
            styles,
        ),
        para("Then open http://127.0.0.1:8001 in the browser.", styles),
        callout(
            "Important",
            "Live GCP mode makes billable Vertex AI and Speech-to-Text calls. Use mock mode only for developer checks; the normal user-facing test path should be GCP live.",
            styles,
        ),
        heading("6. How To Use The UI", styles),
        numbers(
            [
                "Choose the input type: Text, Voice upload, or Video upload.",
                "For Text, paste notes, transcript text, source material, or a structured brief.",
                "For Voice or Video, upload the file. The UI deletes the temporary upload after the graph returns.",
                "Optionally paste an Agent 03 blog brief JSON into the Agent 03 field.",
                "Click Generate Blog.",
                "Read the result page: status, notes, provider, total cost, quality score, stage costs, summary, and draft.",
            ],
            styles,
        ),
        heading("7. What Good Input Looks Like", styles),
        para("Agent 01 performs best when the input includes the actual source idea, not only a command like 'write about AI'.", styles),
        bullets(
            [
                "Topic or working title.",
                "Target audience.",
                "Main idea or argument.",
                "3 to 6 supporting points.",
                "Tone and style preference.",
                "CTA or intended reader action.",
                "Any claims that need evidence, marked clearly as placeholders if not yet verified.",
            ],
            styles,
        ),
        heading("Copy-Paste Text Test Case", styles, level=2),
        code_block(
            """
Topic: How AI agents improve content marketing for B2B teams
Audience: B2B marketing managers and content leads
Tone: clear, practical, confident
Goal: explain a safe, human-reviewed content workflow

Source material:
B2B content teams often lose time turning scattered campaign notes, call
transcripts, and rough ideas into usable briefs. AI agents can help with
repeatable steps such as summarizing source material, creating outlines,
drafting first-pass sections, suggesting titles, and preparing review packages.
The best use case is not replacing editors. It is giving editors a cleaner
starting point so they can spend more time on judgment, accuracy, brand voice,
and final approval. Teams should start with one low-risk workflow, such as blog
draft preparation, and measure time saved before scaling.

CTA: Audit one repeatable content workflow this week.
""",
            styles,
        ),
        PageBreak(),
        heading("8. Agent 03 Blog Brief Handoff", styles),
        para(
            "Agent 01 can accept a structured blog brief from Agent 03. When present, that brief becomes the primary source for audience, goal, angle, outline, CTA, keywords, constraints, evidence placeholders, and risk flags.",
            styles,
        ),
        code_block(
            """
{
  "selected_idea_id": "idea_01",
  "selected_idea_title": "How AI Agents Help B2B Teams Scale Content",
  "suggested_title": "How AI Agents Help B2B Teams Scale Content",
  "title_options": [
    "How AI Agents Help B2B Teams Scale Content",
    "A Practical Guide to Human-Reviewed AI Content Workflows"
  ],
  "target_audience": "B2B marketing managers",
  "campaign_goal": "Build awareness for safe AI-assisted content workflows",
  "content_angle": "Show how agents reduce repetitive content operations while humans keep editorial control.",
  "core_message": "AI agents help content teams scale planning, drafting, and review without removing human judgment.",
  "pain_points": [
    "Campaign notes are scattered across calls, docs, and chats.",
    "Editors spend too much time preparing first drafts.",
    "Teams need speed without losing accuracy or brand voice."
  ],
  "value_proposition": "A repeatable agent-assisted workflow gives teams a cleaner first draft and a stronger review process.",
  "suggested_outline": [
    "Why content teams get stuck",
    "Where AI agents help",
    "Why human review still matters",
    "How to start safely"
  ],
  "proof_points_or_placeholders": [
    "Add internal time-saved evidence if available."
  ],
  "cta": "Audit one repeatable content workflow this week.",
  "tone": "clear, practical, confident",
  "keywords": ["AI agents", "content marketing", "content workflow"],
  "constraints": [
    "Do not invent statistics.",
    "Keep evidence placeholders visible when proof is missing."
  ],
  "risk_flags": ["evidence_placeholder_needed"],
  "quality_notes": ["Use specific workflow examples instead of hype."]
}
""",
            styles,
        ),
        heading("9. Cost, Quality, And Safety", styles),
        bullets(
            [
                "Cost ceiling: every blog run is protected by a hard Rs 50 ceiling.",
                "Quality pass: score must be at least 80 out of 100 and no hard-fail flag may be present.",
                "Revision loop: the graph may revise weak drafts within configured revision and cost caps.",
                "Prompt injection defense: pasted text, transcripts, and reference material are treated as untrusted data, never instructions.",
                "Originality: reference content can inspire structure or context, but the draft must not copy or spin it.",
                "Privacy: raw voice/video uploads are temporary and deleted after processing; run result JSON stays local under apps/blog-ui/runs.",
            ],
            styles,
        ),
        heading("10. Troubleshooting", styles),
        info_table(
            ["Symptom", "Likely cause", "Fix"],
            [
                ["Page says GCP env vars missing", "The PowerShell window running uvicorn does not have the vars set.", "Stop uvicorn, set BLOG_UI_PROVIDER, VERTEX_AI_PROJECT, and GCS_BLOG_BUCKET, then restart."],
                ["Result says needs_human", "Input is too thin, too command-like, unsafe, or missing support.", "Add source material, supporting points, audience, tone, and CTA."],
                ["Provider is mock or output contains mock text", "Server started in mock/offline mode.", "Stop uvicorn, set BLOG_UI_PROVIDER=gcp, restart."],
                ["Voice or video fails", "Upload format, transcription, GCS, or GCP auth issue.", "Check terminal logs, verify ADC/GitHub/GCP setup, and retry with a small file."],
                ["Cost is high", "Long source material or strong-tier draft/review work.", "Use tighter input or split the task into smaller source chunks."],
            ],
            [1.75, 2.25, 2.8],
            styles,
        ),
        heading("11. Operator Checklist", styles),
        bullets(
            [
                "Use live GCP mode for real testing.",
                "Keep the browser form provider-free; provider mode belongs in environment variables.",
                "Do not commit run JSONs or uploaded media.",
                "Check that the final package status is pass before treating it as review-ready.",
                "Manually review facts, claims, brand voice, and citations before publishing outside the agent.",
            ],
            styles,
        ),
        heading("12. Where Files Live", styles),
        info_table(
            ["Area", "Path / behavior"],
            [
                ["Agent logic", "agents/agent-01-blog-writer/agent/"],
                ["UI wrapper", "apps/blog-ui/"],
                ["Run JSONs", "apps/blog-ui/runs/{run_id}.json"],
                ["Temporary uploads", "apps/blog-ui/uploads/ during a request, then deleted"],
                ["Shared providers", "packages/core/providers/"],
                ["Shared tests/evals", "packages/evals/ and agent tests"],
            ],
            [2.0, 4.8],
            styles,
        ),
        para(
            "This guide is for operating Agent 01 v1. It intentionally keeps publishing, web search, scraping, vector retrieval, and visual video analysis outside scope.",
            styles,
        ),
    ]

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return PDF_PATH


if __name__ == "__main__":
    print(build())
