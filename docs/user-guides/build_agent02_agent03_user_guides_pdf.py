"""Build PDF user guides for Agent 02 and Agent 03."""
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
    Spacer,
    Table,
    TableStyle,
)


OUT_DIR = Path(__file__).resolve().parent

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


def footer(label: str):
    def _page_footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.4)
        canvas.line(doc.leftMargin, 0.55 * inch, LETTER[0] - doc.rightMargin, 0.55 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc.leftMargin, 0.35 * inch, label)
        canvas.drawRightString(LETTER[0] - doc.rightMargin, 0.35 * inch, f"Page {doc.page}")
        canvas.restoreState()

    return _page_footer


def build_pdf(path: Path, title: str, subtitle: str, story: list, footer_label: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.75 * inch,
        title=title,
        author="Agents Platform",
        subject=subtitle,
    )
    doc.build(story, onFirstPage=footer(footer_label), onLaterPages=footer(footer_label))
    return path


def agent02_story(styles: dict[str, ParagraphStyle]) -> list:
    return [
        p("Agent 02 Content Repurposer", styles["title"]),
        p("User Guide for the platform-specific content package UI", styles["subtitle"]),
        p(f"Updated: {date.today().isoformat()}  |  Scope: Agent 02 v1  |  Mode: draft-only", styles["meta"]),
        callout(
            "One-line summary",
            "Agent 02 turns an approved long-form article or Agent 01 blog package into review-ready drafts for LinkedIn, Instagram, X/Twitter, short-video script, and optional newsletter/email.",
            styles,
        ),
        heading("1. What Agent 02 Is Trying To Do", styles),
        para(
            "Agent 02 helps marketers turn one approved source asset into channel-native drafts while preserving the original meaning. It is a repurposing agent, not a publishing tool.",
            styles,
        ),
        bullets(
            [
                "Input: raw article text or a serialized passed Agent 01 blog package.",
                "Optional strategy input: Agent 03 repurposing brief JSON.",
                "Output: platform drafts, review package, factual/usefulness/quality reports, hashtags, CTAs, notes, and cost.",
                "Boundary: it never posts, schedules, sends email, writes to a CMS/CRM/ad platform, scrapes, searches, or takes external actions.",
            ],
            styles,
        ),
        heading("2. What It Can And Cannot Do", styles),
        info_table(
            ["Can do", "Cannot do in v1"],
            [
                ["Adapt a source article into platform-specific drafts.", "Publish or schedule posts."],
                ["Use Agent 03 campaign direction as strategy guidance.", "Treat Agent 03 brief as factual source material by itself."],
                ["Create LinkedIn, Instagram, X/Twitter, short-video, and optional newsletter/email drafts.", "Call social platform, CMS, CRM, ad, or email APIs."],
                ["Check factual consistency against the source.", "Invent facts, statistics, or unsupported claims."],
                ["Stop before the Rs 30 package cost ceiling.", "Bypass provider abstractions or cloud-neutral rules."],
            ],
            [3.4, 3.4],
            styles,
        ),
        heading("3. How The Repurposing Pipeline Works", styles),
        numbers(
            [
                "Intake validates the source type, campaign fields, target platforms, and optional Agent 03 brief.",
                "Validate source checks that the source is thick enough and, for Agent 01 packages, review-ready.",
                "Parse source extracts usable text and source claims.",
                "Core message and audience value are extracted from the source and campaign context.",
                "The agent selects platform strategy and loads deterministic platform rules.",
                "Platform drafts are generated through LLMProvider, then finished and validated.",
                "Factual consistency, usefulness, and quality review decide pass, revise, needs_human, or cost stop.",
                "Finalize assembles the RepurposedContentPackage.",
            ],
            styles,
        ),
        heading("4. Output Statuses", styles),
        info_table(
            ["Status", "Meaning", "What to do"],
            [
                ["pass", "Quality score is at least 85, source meaning is preserved, and no hard-fail exists.", "Review and manually publish outside the agent."],
                ["needs_more_input", "The source is too thin or missing required content.", "Add title, summary, source body, audience, goal, and CTA."],
                ["needs_human", "A hard-fail or unrecovered quality issue remains.", "Review hard-fail codes and improve source/campaign context."],
                ["stopped_cost_ceiling", "The Rs 30 ceiling protected the run.", "Use shorter source content or fewer platforms."],
                ["error", "A config/provider/unexpected failure happened.", "Check the terminal running uvicorn."],
            ],
            [1.35, 3.05, 2.4],
            styles,
        ),
        PageBreak(),
        heading("5. How To Start The UI In Live GCP Mode", styles),
        code_block(
            r'''
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"

$repo = (Get-Location).Path
$env:VERTEX_AI_PROJECT = "agents-platform-1212"
$env:PYTHONPATH = "$repo\packages;$repo\agents\agent-02-content-repurposer"

Set-Location "$repo\apps\agent-02-ui"
& "$repo\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8002
''',
            styles,
        ),
        para("Open http://127.0.0.1:8002. If a different server already uses that port, choose another port and open that URL.", styles),
        heading("6. How To Use The UI", styles),
        numbers(
            [
                "Choose source type: Raw article text or Agent 01 blog package.",
                "Fill Title. This is required; missing it causes an error before billable work.",
                "Paste Summary and Full blog/article text. The source text remains the factual base.",
                "Fill audience, brand tone, campaign goal, CTA, and target platforms.",
                "Optional: paste Agent 03 repurposing brief JSON into the dedicated textarea.",
                "Click Generate Package and review platform drafts, hard-fails, suggestions, validation reports, and cost.",
            ],
            styles,
        ),
        callout(
            "Important handoff rule",
            "Agent 03's repurposing brief guides strategy, hooks, tone, CTA, and platform direction. It does not replace the source article. Agent 02 still needs a title plus real source text or an Agent 01 package.",
            styles,
        ),
        heading("7. Working Raw Article Test Case", styles),
        para(
            "Use this as the minimum shape for a passing Agent 02 raw-article run. The important part is the Full blog/article text: it must be real source content, not only a topic, CTA, or Agent 03 strategy brief.",
            styles,
        ),
        code_block(
            """
Source type: raw_article_text
Title: How AI Agents Help B2B Teams Scale Content
Summary: A practical guide to using AI agents for content planning,
drafting, review, and repurposing without removing human editorial
judgment.
Audience: B2B marketing managers
Brand tone: clear, practical, confident
Campaign goal: create review-ready social drafts from one approved article
CTA: Audit one repeatable content workflow this week.
Full blog/article text:
AI agents are becoming useful inside B2B content teams because they
reduce the repetitive work that usually sits between strategy and a
review-ready draft. A campaign often starts with scattered notes,
sales-call themes, webinar transcripts, product positioning, and a few
examples from past launches. Without a system, those inputs become a
slow manual handoff. The team has to clarify the audience, choose an
angle, build an outline, draft the piece, and then repurpose it for
social channels.

The strongest use case is not replacing editors. The practical value is
turning messy approved inputs into structured work that a human can
review. An AI agent can normalize the source material, identify the main
idea, propose a blog plan, draft the article, and prepare a quality
report. A second agent can then repurpose the approved article into
LinkedIn posts, short-video scripts, newsletter copy, and X/Twitter
threads while preserving the original message.

This workflow gives marketing managers two advantages. First, it
reduces handoff friction. Instead of asking every writer to interpret the
same messy brief from scratch, the team starts from a consistent review
package. Second, it improves governance. The agent can be instructed to
avoid unsupported statistics, keep evidence placeholders visible, and
flag content that needs human review before anything is published.

Human review remains essential. Editors still decide whether the angle
is strong, whether the claims are useful, and whether the final draft
matches the brand voice. The agent's role is to make that review easier
by exposing the outline, CTA, assumptions, quality score, and cost. This
keeps automation useful without pretending that the system has live
market research or final publishing authority.

The best starting point is one repeatable workflow. Choose a common
asset, such as a product webinar summary or founder POV article, and run
it through a controlled draft-and-review process. Measure whether the
team saves time, whether the message stays consistent, and whether the
final output still feels specific to the audience. If that works, expand
to more formats and campaigns.
""",
            styles,
        ),
        heading("8. Agent 03 Repurposing Brief Handoff", styles),
        para(
            "From an Agent 03 result, copy the JSON value at package.repurposing_brief_for_agent_02 from apps/agent-03-ui/runs/{run_id}.json. Paste only that object into Agent 02's Agent 03 repurposing brief JSON field.",
            styles,
        ),
        code_block(
            """
{
  "core_message": "AI agents help B2B teams scale content safely when humans keep editorial control.",
  "target_audience": "B2B marketing managers",
  "recommended_platforms": ["linkedin", "newsletter", "short_video"],
  "platform_direction": [
    {"platform": "linkedin", "direction": "Practical post for content leads"},
    {"platform": "newsletter", "direction": "Educational note with workflow steps"}
  ],
  "hooks": ["Your content bottleneck may not be writing; it may be handoff."],
  "cta": "Audit one repeatable workflow before scaling AI-assisted content.",
  "tone_rules": ["Clear", "Specific", "No hype"],
  "content_pillars": ["Workflow design", "Human review", "Safe automation"],
  "message_guardrails": ["Do not invent benchmarks."],
  "repurposing_focus": "Turn a strategic blog into channel-native review drafts."
}
""",
            styles,
        ),
        heading("9. Cost, Quality, And Safety", styles),
        bullets(
            [
                "Hard ceiling: Rs 30/package.",
                "Pass threshold: quality score >= 85 and no hard-fails.",
                "Factual consistency should preserve the source meaning and avoid unsupported claims.",
                "Prompt injection and confidential/internal markers are guarded.",
                "Raw source text and drafts are not logged through telemetry.",
            ],
            styles,
        ),
        heading("10. Troubleshooting", styles),
        info_table(
            ["Symptom", "Likely cause", "Fix"],
            [
                ["Title is required", "Title field was blank.", "Fill Title even when using an Agent 03 brief."],
                ["needs_more_input", "Source body or summary is too thin.", "Paste a fuller article, Agent 01 package, or approved source."],
                ["needs_human", "Quality/factual/platform gate failed.", "Read hard-fails and improvement suggestions."],
                ["No GCP provider", "VERTEX_AI_PROJECT or ADC missing.", "Set env vars in the same terminal and restart uvicorn."],
                ["Generic drafts", "Source or campaign context is too broad.", "Add audience, CTA, tone, source details, and Agent 03 strategy brief."],
            ],
            [1.65, 2.3, 2.85],
            styles,
        ),
        heading("11. Where Files Live", styles),
        info_table(
            ["Area", "Path / behavior"],
            [
                ["Agent logic", "agents/agent-02-content-repurposer/agent/"],
                ["UI wrapper", "apps/agent-02-ui/"],
                ["Run JSONs", "apps/agent-02-ui/runs/{run_id}.json"],
                ["Config", "agents/agent-02-content-repurposer/config/"],
                ["Tests/evals", "agents/agent-02-content-repurposer/tests/"],
            ],
            [2.0, 4.8],
            styles,
        ),
    ]


def agent03_story(styles: dict[str, ParagraphStyle]) -> list:
    return [
        p("Agent 03 Content Ideation Agent", styles["title"]),
        p("User Guide for campaign ideation and downstream handoffs", styles["subtitle"]),
        p(f"Updated: {date.today().isoformat()}  |  Scope: Agent 03 v1  |  Mode: strategy package only", styles["meta"]),
        callout(
            "One-line summary",
            "Agent 03 turns campaign context into a review-ready Content Ideation Package, including a Blog Brief for Agent 01 and a Repurposing Brief for Agent 02.",
            styles,
        ),
        heading("1. What Agent 03 Is Trying To Do", styles),
        para(
            "Agent 03 sits before writing and repurposing. It converts vague campaign notes into themes, content ideas, hooks, CTAs, risk flags, and structured handoff briefs.",
            styles,
        ),
        bullets(
            [
                "Input: campaign goal, product/service, audience, industry, tone, key message, optional keywords/notes/constraints, and number of ideas.",
                "Output: campaign summary, audience insights, themes, ranked ideas, hooks, CTA suggestions, risk flags, quality score, and downstream briefs.",
                "Handoff: blog_brief_for_agent_01 and repurposing_brief_for_agent_02.",
                "Boundary: it does not write the finished blog, repurpose a full source asset, publish, scrape, search, or call Agent 01/02 code directly.",
            ],
            styles,
        ),
        heading("2. What It Can And Cannot Do", styles),
        info_table(
            ["Can do", "Cannot do in v1"],
            [
                ["Generate campaign themes, ideas, hooks, and CTAs.", "Write or publish the final blog."],
                ["Produce structured handoff briefs for Agents 01 and 02.", "Directly run Agent 01 or Agent 02."],
                ["Flag unsupported numerical claims and live research requests.", "Search the web, scrape trends, use SEO tools, or fetch analytics."],
                ["Score ideation quality and risk handling.", "Schedule, post, write to CMS/CRM, or call marketing platforms."],
                ["Stop before the Rs 20 package cost ceiling.", "Invent evidence or claim live research was performed."],
            ],
            [3.4, 3.4],
            styles,
        ),
        heading("3. How The Ideation Pipeline Works", styles),
        numbers(
            [
                "Intake builds the campaign request from form fields.",
                "Validate campaign brief checks required and minimum context.",
                "Analyze audience turns the target audience into pain points and expectations.",
                "Generate themes, ideas, hooks, and CTA suggestions.",
                "Create Blog Brief for Agent 01.",
                "Create Repurposing Brief for Agent 02.",
                "Quality scoring checks relevance, audience fit, specificity, downstream usability, originality, brand fit, and risk handling.",
                "Assemble ContentIdeationPackage with status, notes, handoff briefs, and cost.",
            ],
            styles,
        ),
        heading("4. Output Statuses", styles),
        info_table(
            ["Status", "Meaning", "What to do"],
            [
                ["pass", "Quality score is at least 80, at least one usable idea exists, and both handoff briefs exist.", "Use the package or copy handoff JSON to Agent 01/02."],
                ["needs_more_input", "Required campaign context is missing or too thin.", "Fill campaign goal, product, audience, industry, tone, and key message."],
                ["needs_human", "A terminal hard-fail or non-passing quality gate remains.", "Review notes/risk flags and improve the campaign context."],
                ["stopped_cost_ceiling", "The Rs 20 ceiling protected the run.", "Reduce requested ideas or simplify context."],
                ["error", "A config/provider/unexpected failure happened.", "Check the terminal running uvicorn."],
            ],
            [1.35, 3.05, 2.4],
            styles,
        ),
        PageBreak(),
        heading("5. How To Start The UI In Live GCP Mode", styles),
        code_block(
            r'''
Set-Location "C:\Users\Pranesh\Desktop\agents-platform"

$repo = (Get-Location).Path
$env:AGENT03_UI_PROVIDER = "gcp"
$env:VERTEX_AI_PROJECT = "agents-platform-1212"
$env:PYTHONPATH = "$repo\packages;$repo\agents\agent-03-content-ideation"

Set-Location "$repo\apps\agent-03-ui"
& "$repo\.agent02-ui-venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8003
''',
            styles,
        ),
        para("Open http://127.0.0.1:8003. The page should say Current provider: GCP live.", styles),
        heading("6. How To Use The UI", styles),
        numbers(
            [
                "Fill campaign goal, product/service, industry, target audience, brand tone, and key message.",
                "Add optional keywords, notes, constraints, and preferred formats if useful.",
                "Choose number of ideas, usually 5 to 8 for practical review.",
                "Click Generate Ideas.",
                "Review status, campaign summary, audience insights, themes, ideas, hooks, CTAs, quality, risk flags, and cost.",
                "For downstream work, copy the JSON handoff objects from the saved run file.",
            ],
            styles,
        ),
        heading("7. Sample Campaign Input", styles),
        code_block(
            """
Campaign goal: Build awareness for AI-assisted content workflows
Product/service: ContentIQ
Industry: B2B SaaS
Target audience: B2B marketing managers at growing SaaS companies
Brand tone: clear, practical, confident
Key message: AI agents help teams turn campaign context into structured ideas, briefs, and review-ready drafts while humans keep editorial control.
Optional keywords: AI agents, content planning, content automation
Optional notes: Emphasize safe workflows, human review, and starting with one repeatable process.
Constraints: Do not invent statistics. Avoid hype. Keep evidence placeholders visible.
Number of ideas: 8
""",
            styles,
        ),
        heading("8. How To Send Agent 03 Output To Agent 01", styles),
        numbers(
            [
                "Open the Agent 03 run JSON: apps/agent-03-ui/runs/{run_id}.json.",
                "Find package.blog_brief_for_agent_01.",
                "Copy that object only, including its braces.",
                "Open Agent 01 UI.",
                "Leave Text input blank if you want the brief to be the main source, or add extra source notes if needed.",
                "Paste the object into Agent 03 blog brief JSON.",
                "Generate the blog. The blog should follow the selected idea, audience, outline, CTA, tone, constraints, and risk flags.",
            ],
            styles,
        ),
        code_block(
            """
{
  "selected_idea_id": "idea_01",
  "suggested_title": "How AI Agents Help B2B Teams Scale Content",
  "title_options": ["How AI Agents Help B2B Teams Scale Content"],
  "target_audience": "B2B marketing managers",
  "campaign_goal": "Build awareness for AI-assisted content workflows",
  "content_angle": "Practical workflow adoption without removing human review",
  "core_message": "AI agents help content teams scale repetitive work safely.",
  "suggested_outline": [
    "Why content teams get stuck",
    "Where agents help",
    "Why human review still matters",
    "How to start safely"
  ],
  "tone": "clear, practical, confident",
  "cta": "Audit one repeatable content workflow this week.",
  "constraints": ["Do not invent statistics."]
}
""",
            styles,
        ),
        heading("9. How To Send Agent 03 Output To Agent 02", styles),
        numbers(
            [
                "Open the Agent 03 run JSON: apps/agent-03-ui/runs/{run_id}.json.",
                "Find package.repurposing_brief_for_agent_02.",
                "Copy that object only, including its braces.",
                "Open Agent 02 UI.",
                "Still fill Title, Summary, and Full blog/article text. Agent 02 needs real source content.",
                "Paste the object into Agent 03 repurposing brief JSON.",
                "Generate the package. The drafts should follow the brief's audience, hooks, CTA, tone rules, platform direction, and guardrails.",
            ],
            styles,
        ),
        callout(
            "Common mistake",
            "Do not paste only the Agent 03 brief into Agent 02 and leave Title/source blank. Agent 02 will correctly reject that because a repurposing brief is strategy, not source content.",
            styles,
        ),
        code_block(
            """
{
  "core_message": "AI agents help B2B teams scale content safely.",
  "target_audience": "B2B marketing managers",
  "recommended_platforms": ["linkedin", "instagram", "x_twitter", "short_video"],
  "platform_direction": [
    {"platform": "linkedin", "direction": "Strategic lesson for marketing managers"},
    {"platform": "short_video", "direction": "Simple workflow explanation"}
  ],
  "hooks": ["Your content bottleneck may be handoff, not writing."],
  "cta": "Audit one repeatable content workflow this week.",
  "tone_rules": ["Clear", "Practical", "No hype"],
  "content_pillars": ["Workflow design", "Human review", "Safe automation"],
  "message_guardrails": ["Do not invent benchmarks."],
  "repurposing_focus": "Turn the approved blog/source into channel-native drafts."
}
""",
            styles,
        ),
        heading("10. Cost, Quality, And Safety", styles),
        bullets(
            [
                "Hard ceiling: Rs 20/package.",
                "Pass threshold: quality score >= 80 and no terminal hard-fails.",
                "Warning risk flags can remain on a passing package for human review.",
                "Optional notes are untrusted data, not instructions.",
                "No web search, scraping, trend research, or analytics calls are performed in v1.",
            ],
            styles,
        ),
        heading("11. Troubleshooting", styles),
        info_table(
            ["Symptom", "Likely cause", "Fix"],
            [
                ["needs_more_input", "Required campaign context missing.", "Fill all required fields and use specific key message."],
                ["needs_human", "Risk or quality issue remains.", "Read quality notes and risk flags; remove unsupported claims or improve specificity."],
                ["No blog brief", "Quality gate failed or input too thin.", "Improve campaign context and rerun."],
                ["Agent 01 rejects pasted brief", "Copied the wrong JSON wrapper or malformed JSON.", "Copy only package.blog_brief_for_agent_01 from the run JSON."],
                ["Agent 02 says Title is required", "Agent 02 source title blank.", "Fill Agent 02 Title and source content; then paste the repurposing brief."],
            ],
            [1.65, 2.3, 2.85],
            styles,
        ),
        heading("12. Where Files Live", styles),
        info_table(
            ["Area", "Path / behavior"],
            [
                ["Agent logic", "agents/agent-03-content-ideation/agent/"],
                ["UI wrapper", "apps/agent-03-ui/"],
                ["Run JSONs", "apps/agent-03-ui/runs/{run_id}.json"],
                ["Contracts", "agents/agent-03-content-ideation/agent/contracts.py"],
                ["Tests/evals", "agents/agent-03-content-ideation/tests/"],
            ],
            [2.0, 4.8],
            styles,
        ),
    ]


def build() -> tuple[Path, Path]:
    styles = _styles()
    agent02_pdf = build_pdf(
        OUT_DIR / "agent-02-content-repurposer-user-guide.pdf",
        "Agent 02 Content Repurposer User Guide",
        "How to use Agent 02",
        agent02_story(styles),
        "Agent 02 Content Repurposer Guide",
    )
    agent03_pdf = build_pdf(
        OUT_DIR / "agent-03-content-ideation-user-guide.pdf",
        "Agent 03 Content Ideation User Guide",
        "How to use Agent 03 and hand off to Agent 01/02",
        agent03_story(styles),
        "Agent 03 Content Ideation Guide",
    )
    return agent02_pdf, agent03_pdf


if __name__ == "__main__":
    for built in build():
        print(built)
