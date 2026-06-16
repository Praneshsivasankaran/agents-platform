"""Scoring and risk checks for Agent 05."""
from __future__ import annotations

from .schemas import (
    Agent05Request,
    BalanceGapAnalysis,
    ContentBriefPackage,
    EditorialQualityScore,
    HARD_FAIL_CODES,
    RepurposingMapPackage,
    RiskFlag,
    RiskReport,
    TopicPlanPackage,
)
from .tools import (
    detect_external_action_requests,
    detect_prompt_injection_markers,
    detect_topic_overlap,
    detect_unsupported_claim_markers,
    days_in_range,
    score_pillar_balance,
    score_platform_balance,
)


def _risk(code: str, message: str, *, affected: tuple[str, ...] = (), fix: str = "") -> RiskFlag:
    severity = "hard_fail" if code in HARD_FAIL_CODES else "warning"
    return RiskFlag(
        code=code,  # type: ignore[arg-type]
        severity=severity,
        message=message,
        affected_items=affected,
        recommended_fix=fix,
    )


def _dedupe_flags(flags: list[RiskFlag]) -> tuple[RiskFlag, ...]:
    seen: set[str] = set()
    out: list[RiskFlag] = []
    for flag in flags:
        key = f"{flag.code}:{','.join(flag.affected_items)}"
        if key not in seen:
            out.append(flag)
            seen.add(key)
    return tuple(out)


def build_risk_report(
    *,
    request: Agent05Request | None,
    validation_errors: tuple[str, ...] = (),
    topic_plan: TopicPlanPackage | None,
    content_briefs: ContentBriefPackage | None,
    repurposing: RepurposingMapPackage | None,
    balance_gap_analysis: BalanceGapAnalysis | None,
) -> RiskReport:
    flags: list[RiskFlag] = []

    if validation_errors:
        flags.append(
            _risk(
                "empty_or_invalid_output",
                "Request validation failed before a review-ready plan could be generated.",
                affected=validation_errors,
                fix="Provide all required editorial planning fields with a valid date range.",
            )
        )

    if request is None:
        risk_flags = _dedupe_flags(flags)
        hard_fails = tuple(flag.code for flag in risk_flags if flag.severity == "hard_fail")
        return RiskReport(risk_flags=risk_flags, hard_fail_codes=hard_fails, passed=not hard_fails)

    combined_user_context = " ".join(
        (
            request.business_goal,
            request.campaign_theme,
            " ".join(request.existing_ideas),
            " ".join(request.constraints),
        )
    )
    if detect_prompt_injection_markers(combined_user_context):
        flags.append(
            _risk(
                "prompt_injection_marker",
                "Input contains prompt-injection style text; it must be treated only as data.",
                fix="Review the affected idea or constraint before using the plan.",
            )
        )
    if detect_external_action_requests(combined_user_context):
        flags.append(
            _risk(
                "external_action_claimed",
                "Input requests publishing, scheduling, calendar, social, email, or CMS actions.",
                fix="Keep v1 output planning-only and remove external action instructions.",
            )
        )
    if detect_unsupported_claim_markers(combined_user_context):
        flags.append(
            _risk(
                "unsafe_or_unsupported_claims",
                "Input contains unsupported claims that require human verification.",
                fix="Add evidence or reword claims as review notes.",
            )
        )

    items = topic_plan.items if topic_plan else ()
    briefs = content_briefs.briefs if content_briefs else ()
    if not items:
        flags.append(_risk("missing_editorial_calendar", "Editorial calendar items are missing."))
    if not briefs:
        flags.append(_risk("missing_content_briefs", "Content briefs are missing."))

    planned_platforms = tuple(item.platform for item in items)
    missing_platforms = tuple(platform for platform in request.platforms if platform not in planned_platforms)
    if items and missing_platforms:
        flags.append(
            _risk(
                "missing_platform_coverage",
                "One or more requested platforms have no planned items.",
                affected=missing_platforms,
                fix="Add at least one item for each requested platform or explain why it is excluded.",
            )
        )
    if items and set(planned_platforms).isdisjoint(set(request.platforms)):
        flags.append(_risk("platform_list_ignored", "The requested platform list was not respected."))

    try:
        expected_count = max(1, days_in_range(request.date_range.start, request.date_range.end))
    except Exception:
        expected_count = 0
    out_of_range = tuple(
        item.slot_id
        for item in items
        if item.planned_date < request.date_range.start or item.planned_date > request.date_range.end
    )
    if out_of_range or expected_count == 0:
        flags.append(
            _risk(
                "date_range_not_respected",
                "One or more planned dates fall outside the requested date range.",
                affected=out_of_range,
            )
        )

    if request.production_capacity_per_week and len(items) > request.production_capacity_per_week * 8:
        flags.append(
            _risk(
                "impossible_or_overdense_cadence",
                "The planned volume may exceed the supplied production capacity.",
                fix="Reduce posting frequency or widen the date range.",
            )
        )

    duplicate_topics = detect_topic_overlap(tuple(item.topic for item in items))
    if duplicate_topics:
        flags.append(
            _risk(
                "duplicated_topics",
                "Plan includes duplicate or near-duplicate topics.",
                affected=duplicate_topics,
                fix="Replace duplicates with distinct angles.",
            )
        )

    missing_cta = tuple(item.slot_id for item in items if not item.primary_cta)
    if missing_cta:
        flags.append(
            _risk(
                "missing_cta_direction",
                "Some planned items do not have CTA guidance.",
                affected=missing_cta,
            )
        )

    vague_briefs = tuple(
        brief.brief_id
        for brief in briefs
        if len(brief.outline) < 2 or len(brief.key_message.split()) < 5
    )
    if vague_briefs:
        flags.append(
            _risk(
                "vague_or_unactionable_briefs",
                "Some briefs are too thin to guide content creation.",
                affected=vague_briefs,
                fix="Add key message, outline, CTA, and review notes.",
            )
        )

    repurpose_items = repurposing.items if repurposing else ()
    if len(request.platforms) > 1 and not repurpose_items:
        flags.append(
            _risk(
                "thin_repurposing_map",
                "Multi-platform plan lacks repurposing guidance.",
                fix="Map core items to secondary platforms with adaptation notes.",
            )
        )

    if balance_gap_analysis:
        for count in balance_gap_analysis.pillar_counts:
            if count.count == 0:
                flags.append(
                    _risk(
                        "underused_content_pillars",
                        "A requested content pillar has no planned coverage.",
                        affected=(count.name,),
                    )
                )

    risk_flags = _dedupe_flags(flags)
    hard_fails = tuple(flag.code for flag in risk_flags if flag.severity == "hard_fail")
    return RiskReport(risk_flags=risk_flags, hard_fail_codes=hard_fails, passed=not hard_fails)


def score_output(
    *,
    request: Agent05Request | None,
    topic_plan: TopicPlanPackage | None,
    content_briefs: ContentBriefPackage | None,
    repurposing: RepurposingMapPackage | None,
    balance_gap_analysis: BalanceGapAnalysis | None,
    risk_report: RiskReport,
    validation_errors: tuple[str, ...] = (),
) -> EditorialQualityScore:
    items = topic_plan.items if topic_plan else ()
    briefs = content_briefs.briefs if content_briefs else ()
    repurpose_items = repurposing.items if repurposing else ()

    input_completeness = 0 if validation_errors or request is None else 10

    calendar_coverage = 0
    if request is not None and items:
        calendar_coverage = 8
        if all(request.date_range.start <= item.planned_date <= request.date_range.end for item in items):
            calendar_coverage += 4
        if len(items) >= min(3, len(request.platforms) * 2):
            calendar_coverage += 3
    calendar_coverage = min(15, calendar_coverage)

    audience_goal_alignment = 0
    if request is not None and items:
        context = f"{request.business_goal} {request.target_audience} {request.campaign_theme}".lower()
        hits = sum(
            1
            for item in items
            if any(token in (item.objective + " " + item.topic).lower() for token in context.split() if len(token) > 4)
        )
        audience_goal_alignment = 8 + min(7, hits)

    platform_fit = 0
    if request is not None and items:
        used = tuple(item.platform for item in items)
        platform_fit = 5 + min(10, score_platform_balance(used, request.platforms))

    pillar_balance = 0
    if request is not None and items:
        used_pillars = tuple(item.pillar for item in items)
        pillar_balance = score_pillar_balance(used_pillars, request.content_pillars)

    brief_actionability = 0
    if briefs:
        complete = sum(1 for brief in briefs if brief.key_message and brief.outline and brief.cta_suggestions)
        brief_actionability = min(15, 6 + int((complete / len(briefs)) * 9))

    repurposing_usefulness = 0
    if request is not None:
        if len(request.platforms) <= 1:
            repurposing_usefulness = 10
        elif repurpose_items:
            repurposing_usefulness = min(10, 4 + len(repurpose_items) * 2)

    risk_safety = 10
    if risk_report.hard_fail_codes:
        risk_safety = 0
    elif risk_report.risk_flags:
        risk_safety = max(4, 10 - len(risk_report.risk_flags))

    total_score = (
        input_completeness
        + calendar_coverage
        + audience_goal_alignment
        + platform_fit
        + pillar_balance
        + brief_actionability
        + repurposing_usefulness
        + risk_safety
    )
    return EditorialQualityScore(
        input_completeness=input_completeness,
        calendar_coverage=calendar_coverage,
        audience_goal_alignment=min(15, audience_goal_alignment),
        platform_fit=min(15, platform_fit),
        pillar_balance=min(10, pillar_balance),
        brief_actionability=min(15, brief_actionability),
        repurposing_usefulness=min(10, repurposing_usefulness),
        risk_safety=risk_safety,
        total_score=min(100, total_score),
        passed=total_score >= 80 and not risk_report.hard_fail_codes,
        hard_fail_codes=risk_report.hard_fail_codes,
    )

