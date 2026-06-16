"""Build the Agent 04 SEO Optimizer user guide PDF."""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from typing import Iterable

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
    Table,
    TableStyle,
)


OUT_DIR = Path(__file__).resolve().parent
PDF_PATH = OUT_DIR / "agent-04-seo-optimizer-user-guide.pdf"

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
            spaceBefore=15,
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
            fontSize=7.5,
            leading=9.3,
            textColor=colors.HexColor("#111111"),
        ),
    }


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def heading(text: str, styles: dict[str, ParagraphStyle], level: int = 1) -> Paragraph:
    return p(text, styles["h1" if level == 1 else "h2"])


def para(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return p(text, styles["body"])


def bullets(items: Iterable[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, styles["body"]), leftIndent=12) for item in items],
        bulletType="bullet",
        start="circle",
        leftIndent=18,
        bulletFontName="Helvetica",
        bulletFontSize=7,
    )


def numbers(items: Iterable[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, styles["body"]), leftIndent=16) for item in items],
        bulletType="1",
        leftIndent=20,
        bulletFontName="Helvetica",
        bulletFontSize=8,
    )


def code_block(text: str, styles: dict[str, ParagraphStyle]) -> Table:
    block = Preformatted(text.strip("\n"), styles["code"])
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
    canvas.drawString(doc.leftMargin, 0.35 * inch, "Agent 04 SEO Optimizer Guide")
    canvas.drawRightString(LETTER[0] - doc.rightMargin, 0.35 * inch, f"Page {doc.page}")
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
        title="Agent 04 SEO Optimizer User Guide",
        author="Agents Platform",
        subject="How to use Agent 04 SEO Optimizer",
    )

    story = [
        p("Agent 04 SEO Optimizer", styles["title"]),
        p("User Guide for review-ready SEO optimization packages", styles["subtitle"]),
        p(f"Updated: {date.today().isoformat()}  |  Scope: Agent 04 v1  |  Mode: draft-only", styles["meta"]),
        callout(
            "One-line summary",
            "Agent 04 takes an existing blog or article draft and returns a review-ready SEO optimization package: metadata, slug, headings, keyword placement, FAQs, readability fixes, risk flags, cost, and an optimized draft. It does not publish or call external SEO tools.",
            styles,
        ),
        heading("1. What Agent 04 Is Trying To Do", styles),
        para(
            "Agent 04 sits after writing and before repurposing. It improves an already-written draft so a human editor can review SEO recommendations faster and more consistently.",
            styles,
        ),
        bullets(
            [
                "Input: draft content, topic/title, primary keyword, optional secondary keywords, audience, content goal, tone, constraints, and CTA direction.",
                "Output: SEO title options, meta description, URL slug, recommended H1, heading plan, keyword placement, readability fixes, FAQs, risk flags, SEO score, cost, and optimized draft.",
                "Boundary: it is review-only. It does not publish, scrape, search, call SEO APIs, fetch analytics, write to CMS, or post to social platforms.",
                "Provider path: live model calls go through the shared LLMProvider/LiteLLM abstraction, selected by config.",
            ],
            styles,
        ),
        heading("2. What It Can And Cannot Do", styles),
        info_table(
            ["Can do", "Cannot do in v1"],
            [
                ["Improve metadata, headings, slug, readability, CTA, FAQs, and keyword placement.", "Publish, schedule, or send content anywhere."],
                ["Score the output using a 100-point SEO rubric.", "Use Google Search Console, Analytics, keyword-volume APIs, or backlink tools."],
                ["Flag missing keywords, weak headings, unsupported claims, repetition, and injection markers.", "Scrape live search results, competitor pages, or social platforms."],
                ["Run in mock mode or GCP/Vertex mode through config.", "Import cloud SDKs or direct model SDKs inside agent logic."],
                ["Save local UI run JSONs for review.", "Keep long-term memory or learn across requests."],
            ],
            [3.4, 3.4],
            styles,
        ),
        heading("3. How The SEO Pipeline Works", styles),
        numbers(
            [
                "Intake validates that draft content, topic/title, and primary keyword are present.",
                "Normalize input cleans whitespace, parses keywords and constraints, and prepares typed Agent04Request data.",
                "Analyze existing draft computes word count, headings, keyword presence, readability, intro/CTA signals, and draft issues.",
                "Plan keywords builds a primary and secondary keyword placement plan.",
                "Generate metadata recommends SEO titles, meta description, URL slug, and H1 through LLMProvider with deterministic fallback.",
                "Optimize headings creates an H1/H2/H3 structure.",
                "Review readability suggests intro, conclusion, CTA, and readability fixes.",
                "Generate FAQs proposes FAQ questions and answers.",
                "Optimize draft produces a review-ready optimized draft while preserving meaning.",
                "Risk checks and scoring decide pass, needs_human, needs_more_input, stopped_cost_ceiling, or error.",
            ],
            styles,
        ),
        heading("4. Output Statuses", styles),
        info_table(
            ["Status", "Meaning", "What to do"],
            [
                ["pass", "SEO score is at least 80 and no hard-fail risk exists.", "Review the package and manually apply or approve the final content outside the agent."],
                ["needs_more_input", "Required draft, topic, or primary keyword is missing.", "Fill the missing fields and rerun."],
                ["needs_human", "A hard-fail risk or sub-threshold score remains.", "Read risk flags and editor notes, then improve the source draft or keyword brief."],
                ["stopped_cost_ceiling", "The Rs 20 package ceiling protected the run.", "Shorten the draft or reduce complexity before rerun."],
                ["error", "A provider, config, schema, or unexpected issue stopped the run.", "Check the terminal running uvicorn and verify GCP/env setup."],
            ],
            [1.35, 3.05, 2.4],
            styles,
        ),
        PageBreak(),
        heading("5. How To Start The UI In Live GCP Mode", styles),
        para("Open PowerShell and run these from the repository root:", styles),
        code_block(
            r'''
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"

$repo = (Get-Location).Path
$env:AGENT04_UI_PROVIDER = "gcp"
$env:VERTEX_AI_PROJECT = "agents-platform-1212"
$env:PYTHONPATH = "$repo\packages;$repo\agents\agent-04-seo-optimizer"

# One-time/auth refresh when needed:
gcloud auth application-default login

Set-Location "$repo\apps\agent-04-ui"
& "$repo\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8004
''',
            styles,
        ),
        para("Open http://127.0.0.1:8004. The page should say Current provider: GCP live.", styles),
        callout(
            "Important",
            "Live GCP mode makes billable Vertex AI calls. If the page shows missing GCP configuration, set VERTEX_AI_PROJECT in the same PowerShell window and authenticate with Google ADC before restarting uvicorn.",
            styles,
        ),
        heading("6. How To Run The Live GCP Smoke Test", styles),
        code_block(
            r'''
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"

$env:PYTHONPATH = "packages;agents\agent-04-seo-optimizer"
$env:VERTEX_AI_PROJECT = "agents-platform-1212"
gcloud auth application-default login

.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-04-seo-optimizer\tests\smoke -m smoke -x -v
''',
            styles,
        ),
        para(
            "The smoke test skips when litellm or VERTEX_AI_PROJECT is missing. When prerequisites are present, it performs one paid live run, verifies the provider is LiteLLM, checks a terminal package, confirms real non-synthetic model usage, validates cost under Rs 20, and reruns the no-cloud-SDK guard.",
            styles,
        ),
        heading("7. How To Use The UI", styles),
        numbers(
            [
                "Paste the full draft content. Agent 04 optimizes an existing draft; it is not a blank-page writing agent.",
                "Fill Topic/title and Primary keyword. These are required.",
                "Optionally add secondary keywords separated by commas or new lines.",
                "Fill audience, brand tone, content goal, CTA direction, and constraints when available.",
                "Click Optimize SEO.",
                "Review the result page: status, SEO score, title options, meta description, slug, H1, heading plan, keyword placement, readability fixes, FAQs, risk flags, cost, editor notes, and optimized draft.",
            ],
            styles,
        ),
        heading("8. Working Draft Test Case", styles),
        para("Use this sample to verify the UI flow before trying your own article:", styles),
        code_block(
            """
Draft content:
Cloud neutral AI agents help engineering and marketing teams avoid platform lock in. A reusable agent platform keeps workflow logic separate from the cloud provider, so the same agent can run with Vertex AI today and another provider later. The practical pattern is to put model calls behind an LLM provider, keep schemas strict, route costs through a shared ledger, and expose every result as a review package. This helps teams test locally, run a live provider smoke test, and keep humans responsible for final approval. A good starting point is one repeatable content workflow where the source draft already exists and the agent only improves structure, metadata, headings, keyword placement, readability, and review notes.

Topic/title: Cloud neutral AI agents
Primary keyword: cloud neutral AI agents
Secondary keywords: agent platform, provider abstraction, SEO workflow
Target audience: engineering and marketing leaders
Brand tone: clear, practical, confident
Content goal: educate readers on a safe reusable agent workflow
CTA direction: Ask for a platform review
Constraints: Do not invent statistics. Keep review-only boundaries clear.
""",
            styles,
        ),
        heading("9. Reading The Output", styles),
        info_table(
            ["Section", "How to use it"],
            [
                ["SEO score", "Use pass/fail plus sub-scores to decide whether the package is review-ready."],
                ["Title/meta/slug/H1", "Copy these into your editor or CMS manually after human review."],
                ["Heading plan", "Use it to restructure the draft without changing meaning."],
                ["Keyword placement", "Check where the primary and secondary keywords appear and where they should be added."],
                ["Readability fixes", "Apply these before final editing."],
                ["FAQ suggestions", "Use only if they fit the article and the claims are supportable."],
                ["Risk flags", "Treat hard-fail risks as blockers until a human resolves them."],
                ["Cost", "Confirm the run stayed under the Rs 20 Agent 04 ceiling."],
            ],
            [2.0, 4.8],
            styles,
        ),
        heading("10. API Test Without Browser", styles),
        para("You can also test the local app as JSON while uvicorn is running:", styles),
        code_block(
            r'''
$body = @{
  draft_content = "Cloud neutral AI agents help teams avoid lock in. Provider abstractions, strict schemas, cost ledgers, and human review gates make agent workflows easier to reuse across clouds."
  topic = "Cloud neutral AI agents"
  primary_keyword = "cloud neutral AI agents"
  secondary_keywords = @("agent platform", "SEO workflow")
  target_audience = "engineering leaders"
  content_goal = "educate"
  brand_tone = "clear and practical"
  cta_direction = "Ask for a platform review"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8004/optimize" -Method Post -ContentType "application/json" -Body $body
''',
            styles,
        ),
        heading("11. Troubleshooting", styles),
        info_table(
            ["Symptom", "Likely cause", "Fix"],
            [
                ["Page says GCP env vars missing", "The uvicorn terminal does not have AGENT04_UI_PROVIDER=gcp and VERTEX_AI_PROJECT set.", "Stop uvicorn, set both variables in the same terminal, authenticate ADC, then restart."],
                ["Smoke test skips", "litellm is not installed in that Python env or VERTEX_AI_PROJECT is unset.", "Use the project venv that has litellm, set VERTEX_AI_PROJECT, and rerun."],
                ["Provider/model error", "ADC is missing, Vertex AI API is unavailable, or the project lacks permissions.", "Run gcloud auth application-default login, verify project access, and check terminal logs."],
                ["needs_more_input", "Draft, topic, or primary keyword was blank.", "Fill all required fields."],
                ["needs_human", "SEO score failed or hard-fail risks were found.", "Read risk flags and improve draft, keyword fit, or evidence support."],
                ["Output feels generic", "The draft or brief is too short or lacks audience/goal/CTA.", "Add a fuller draft, specific audience, content goal, and CTA direction."],
            ],
            [1.55, 2.35, 2.9],
            styles,
        ),
        heading("12. Where Files Live", styles),
        info_table(
            ["Area", "Path / behavior"],
            [
                ["Agent logic", "agents/agent-04-seo-optimizer/agent/"],
                ["UI wrapper", "apps/agent-04-ui/"],
                ["Run JSONs", "apps/agent-04-ui/runs/{run_id}.json"],
                ["Config", "agents/agent-04-seo-optimizer/config/"],
                ["Live smoke", "agents/agent-04-seo-optimizer/tests/smoke/test_smoke_gcp.py"],
                ["Tests/evals", "agents/agent-04-seo-optimizer/tests/"],
            ],
            [2.0, 4.8],
            styles,
        ),
        para(
            "This guide is for operating Agent 04 v1. It intentionally keeps publishing, SEO APIs, analytics, scraping, CMS writes, social posting, auth, database, and long-term memory outside scope.",
            styles,
        ),
    ]

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return PDF_PATH


if __name__ == "__main__":
    print(build())
