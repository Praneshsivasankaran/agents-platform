"""Deterministic Agent 02 validators and scoring helpers."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

from .schemas import (
    Agent02Request,
    AudienceValue,
    ContentAngle,
    CoreMessage,
    DEFAULT_PLATFORMS,
    FactualConsistencyReport,
    HardFail,
    HashtagSet,
    LLMDraftBundle,
    LLMPlatformDraft,
    ParsedSource,
    Platform,
    PlatformDraft,
    PlatformRules,
    PlatformScore,
    PlatformStrategy,
    PlatformValidationResult,
    QualityReport,
    QualitySubScores,
    SourceClaim,
    SourceContent,
    UnsupportedClaim,
    UsefulnessReport,
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"#[A-Za-z][A-Za-z0-9_]*")
_CONFIDENTIAL_RE = re.compile(
    r"\b(confidential|internal only|do not share|private|secret|under nda|not public)\b",
    re.IGNORECASE,
)
_INJECTION_RE = re.compile(
    r"\b(ignore previous instructions|reveal system prompt|developer message|system instruction)\b",
    re.IGNORECASE,
)
# A *claim that an external publishing action was completed* — the spec's terminal hard-fail
# ("Claims that content has been published"). It must NOT fire on incidental marketing mentions
# of publishing as a topic (e.g. "a published blog post", "schedule your posts", "before you
# publish"), which would terminal-fail virtually every legitimate real-model draft. So a bare
# verb is not enough: require a first-person/this-content subject or completed-action framing.
_CONTENT_NOUN = r"(?:post|content|piece|article|thread|video|campaign|newsletter|caption)"
_PUBLISHING_CLAIM_RE = re.compile(
    r"\b(?:"
    # A FIRST-PERSON / this-content subject claiming the (completed) external action. Second-person
    # ("after you've published", "schedule your posts") is advice to the reader, NOT a false claim by
    # the agent, so "you/your" subjects are deliberately excluded to avoid terminal false positives.
    r"(?:we|i|our team|this\s+" + _CONTENT_NOUN + r")"
    r"(?:\s+(?:have|has|had|already|just|now|successfully|finally|been))*"
    r"\s+(?:published|posted|scheduled|uploaded|shared|sent)\b"
    # "this <content> is/was/went (now) live"
    r"|this\s+" + _CONTENT_NOUN + r"\s+(?:is|was|went)\s+(?:now\s+)?live\b"
    r")",
    re.IGNORECASE,
)
_FAKE_STAT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?%|\b\d+x\b|\b\d+\s?(?:lakh|million|billion)\b", re.IGNORECASE)
_EXTERNAL_PROOF_RE = re.compile(
    r"\b(?:"
    r"study|studies|research|survey|benchmark|analysis|whitepaper"
    r"|report\s+(?:shows?|finds?|found|proved?|says|reveals?|confirms?)"
    r"|data\s+(?:shows?|finds?|found|proved?|says|reveals?|confirms?)"
    r"|customers?\s+(?:reported|achieved|saw|saved|increased|decreased|reduced)"
    r"|guarantee[sd]?|proven|proved"
    r")\b",
    re.IGNORECASE,
)
# Human-readable cliché examples — used to steer the model (prompt avoid-clause). Note the
# qualified "unlock your potential" / "unlock growth" rather than the bare word "unlock".
_GENERIC_PHRASES = (
    "game changer",
    "in today's fast-paced world",
    "revolutionize",
    "unlock your potential",
    "unlock growth",
    "transform your business",
    "take it to the next level",
)
# Generic-content detector. Clear multi-word clichés match exactly; "unlock" only fires when paired
# with a cliché object (e.g. "unlock your potential", "unlock growth"), so legitimate copy such as
# "unlock the full guide" / "unlocked the archive" is NOT flagged. This reduces false positives
# without weakening the gate — genuine generic/cliché content still fails.
_GENERIC_RE = re.compile(
    r"game[\s-]?changer"
    r"|in\s+today['’]?s\s+fast[\s-]?paced\s+world"
    r"|revolutioniz(?:e|es|ing|ed)"
    r"|transform\s+your\s+business"
    r"|take\s+it\s+to\s+the\s+next\s+level"
    r"|unlock(?:ing|s|ed)?\s+"
    r"(?:(?:your|the|a|its|their|our|new|true|hidden|massive|explosive|real|full|complete|next)\s+)*"
    r"(?:potential|growth|success|power|results?|opportunit(?:y|ies)|secrets?|gains?)",
    re.IGNORECASE,
)
_WEAK_CTAS = frozenset({"click here", "learn more", "read more", "check it out", "visit now"})


def normalize_platform(value: str) -> Platform:
    key = " ".join(str(value).strip().lower().replace("-", " ").replace("_", " ").split())
    aliases = {
        "linkedin": "linkedin",
        "instagram": "instagram",
        "x": "x_twitter",
        "twitter": "x_twitter",
        "x twitter": "x_twitter",
        "short video": "short_video",
        "short video script": "short_video",
        "video": "short_video",
        "newsletter": "newsletter",
        "email": "newsletter",
        "newsletter email": "newsletter",
    }
    if key not in aliases:
        raise ValueError(f"unsupported platform: {value!r}")
    return aliases[key]  # type: ignore[return-value]


def selected_platforms(request: Agent02Request) -> tuple[Platform, ...]:
    platforms = tuple(dict.fromkeys(request.target_platforms or DEFAULT_PLATFORMS))
    if request.include_newsletter and "newsletter" not in platforms:
        platforms = platforms + ("newsletter",)
    return platforms


def source_body(source: SourceContent) -> str:
    return (source.full_text or source.blog_body or source.summary or source.title).strip()


def validate_source_for_agent02(source: SourceContent) -> tuple[bool, str | None]:
    body = source_body(source)
    words = _WORD_RE.findall(body)
    if source.source_type == "agent01_blog_package" and source.source_status not in (None, "pass"):
        return False, "Agent 01 source package is not status='pass'."
    if len(words) < 80:
        return False, "Source content is too thin; provide at least one complete article or passed blog package."
    if len(split_sentences(body)) < 3:
        return False, "Source content needs at least three substantive sentences."
    return True, None


def split_sentences(text: str) -> tuple[str, ...]:
    raw = _SENTENCE_RE.split(" ".join(str(text or "").split()))
    sentences = tuple(s.strip(" -\n\t") for s in raw if len(_WORD_RE.findall(s)) >= 4)
    return sentences


def extract_claims(source: SourceContent) -> tuple[SourceClaim, ...]:
    body = source_body(source)
    claims: list[SourceClaim] = []
    for idx, sentence in enumerate(split_sentences(body)[:10], start=1):
        claim_type = "statistic" if _FAKE_STAT_RE.search(sentence) else "fact"
        if any(word in sentence.lower() for word in ("should", "can", "helps", "must")):
            claim_type = "recommendation"
        claims.append(
            SourceClaim(
                claim_id=f"c{idx}",
                text=sentence,
                claim_type=claim_type,  # type: ignore[arg-type]
                supported=True,
            )
        )
    return tuple(claims)


def parse_source(source: SourceContent) -> ParsedSource:
    body = source_body(source)
    usable, thin_reason = validate_source_for_agent02(source)
    claims = extract_claims(source) if usable else ()
    confidential = tuple(sorted(set(m.group(0).lower() for m in _CONFIDENTIAL_RE.finditer(body))))
    return ParsedSource(
        title=source.title.strip() or first_words(body, 8),
        summary=source.summary.strip() or first_sentence(body),
        body=body,
        source_claims=claims,
        tone="professional",
        audience_hint="marketing audience",
        cta_hint="review the original content",
        seo_keywords=source.seo_keywords,
        suggested_tags=source.suggested_tags,
        usable=usable,
        thin_reason=thin_reason,
        confidential_flags=confidential,
    )


def build_core_message(parsed: ParsedSource) -> CoreMessage:
    points = tuple(claim.text for claim in parsed.source_claims[:4])
    return CoreMessage(main_message=parsed.summary or parsed.title, supporting_points=points)


def build_audience_value(request: Agent02Request, parsed: ParsedSource) -> AudienceValue:
    audience = request.audience.strip() or parsed.audience_hint or "target readers"
    takeaways = tuple(claim.text for claim in parsed.source_claims[:3])
    pain = ("too much long-form content stays underused", "teams need channel-specific drafts")
    return AudienceValue(
        audience=audience,
        pain_points=pain,
        practical_takeaways=takeaways,
        why_it_matters=f"{parsed.title or 'This content'} gives {audience} a useful reason to act.",
    )


def generate_angles(parsed: ParsedSource, platforms: tuple[Platform, ...]) -> tuple[ContentAngle, ...]:
    insight = parsed.source_claims[0].text if parsed.source_claims else parsed.summary
    practical = parsed.source_claims[1].text if len(parsed.source_claims) > 1 else parsed.summary
    return (
        ContentAngle(
            angle_id="insight",
            title="Lead with the strongest insight",
            platform_fit=platforms,
            rationale=insight,
        ),
        ContentAngle(
            angle_id="practical",
            title="Show the practical takeaway",
            platform_fit=platforms,
            rationale=practical,
        ),
        ContentAngle(
            angle_id="action",
            title="Turn the idea into a next step",
            platform_fit=platforms,
            rationale="Connect the source message to a review-ready CTA.",
        ),
    )


def select_strategy(
    request: Agent02Request,
    platforms: tuple[Platform, ...],
    angles: tuple[ContentAngle, ...],
) -> tuple[PlatformStrategy, ...]:
    angle_cycle = tuple(a.angle_id for a in angles) or ("insight",)
    cta = request.cta.strip() or "Read the full piece and decide what to apply next."
    out: list[PlatformStrategy] = []
    for idx, platform in enumerate(platforms):
        content_type = {
            "linkedin": "post",
            "instagram": "caption",
            "x_twitter": "thread",
            "short_video": "script",
            "newsletter": "email",
        }[platform]
        out.append(
            PlatformStrategy(
                platform=platform,
                content_type=content_type,  # type: ignore[arg-type]
                angle_id=angle_cycle[idx % len(angle_cycle)],
                format_notes=f"{platform} draft should be distinct and native to the channel.",
                cta=cta,
            )
        )
    return tuple(out)


def platform_rules(platforms: tuple[Platform, ...]) -> tuple[PlatformRules, ...]:
    rules: list[PlatformRules] = []
    for platform in platforms:
        if platform == "linkedin":
            rules.append(
                PlatformRules(
                    platform=platform,
                    content_type="post",
                    min_chars=700,
                    max_chars=1300,
                    min_hashtags=0,
                    max_hashtags=5,
                    notes="Professional, insight-driven, clear CTA, avoid casual filler.",
                )
            )
        elif platform == "instagram":
            rules.append(
                PlatformRules(
                    platform=platform,
                    content_type="caption",
                    min_chars=500,
                    max_chars=1200,
                    min_hashtags=5,
                    max_hashtags=12,
                    requires_visual_angle=True,
                    notes="Simple, visual, punchy, easy to skim.",
                )
            )
        elif platform == "x_twitter":
            rules.append(
                PlatformRules(
                    platform=platform,
                    content_type="thread",
                    min_chars=0,
                    max_chars=280,
                    min_hashtags=0,
                    max_hashtags=2,
                    min_thread_posts=4,
                    max_thread_posts=7,
                    notes="Single post <=280 chars or thread with 4-7 non-repeating posts.",
                )
            )
        elif platform == "short_video":
            rules.append(
                PlatformRules(
                    platform=platform,
                    content_type="script",
                    min_chars=0,
                    max_chars=0,
                    min_hashtags=0,
                    max_hashtags=0,
                    min_duration_s=30,
                    max_duration_s=60,
                    notes="Hook in first 3 seconds; include shot direction, VO, on-screen text, CTA.",
                )
            )
        elif platform == "newsletter":
            rules.append(
                PlatformRules(
                    platform=platform,
                    content_type="email",
                    min_chars=250,
                    max_chars=900,
                    min_hashtags=0,
                    max_hashtags=0,
                    notes="Concise subject, preview text, short body, CTA.",
                )
            )
    return tuple(rules)


def make_platform_drafts(
    request: Agent02Request,
    parsed: ParsedSource,
    core: CoreMessage,
    audience_value: AudienceValue,
    strategies: tuple[PlatformStrategy, ...],
) -> tuple[PlatformDraft, ...]:
    claim_one = parsed.source_claims[0].text if parsed.source_claims else parsed.summary
    claim_two = parsed.source_claims[1].text if len(parsed.source_claims) > 1 else core.main_message
    cta = request.cta.strip() or "Read the full piece before your next planning session."
    tags = _safe_hashtags(parsed.suggested_tags or parsed.seo_keywords)
    drafts: list[PlatformDraft] = []
    for strategy in strategies:
        if strategy.platform == "linkedin":
            body = _fit_length(
                "\n\n".join(
                    (
                        "Most teams do not need more content. They need more mileage from the content already worth trusting.",
                        f"The source idea: {claim_one}",
                        f"Why it matters for {audience_value.audience}: {audience_value.why_it_matters}",
                        f"Practical takeaway: {claim_two}",
                        "Use the long-form piece as the anchor, then adapt the angle, proof, and CTA for each channel.",
                        cta,
                    )
                ),
                700,
                1300,
            )
            drafts.append(
                PlatformDraft(
                    platform="linkedin",
                    content_type="post",
                    hook="Most teams do not need more content. They need more mileage from what already works.",
                    body=body,
                    cta=cta,
                    hashtags=tags[:5],
                    why_this_works="It turns the source into a professional point of view with a practical takeaway.",
                    audience_value=audience_value.why_it_matters,
                    usage_notes="Review the claims and adjust brand examples before posting manually.",
                    quality_score=90,
                )
            )
        elif strategy.platform == "instagram":
            body = _fit_length(
                "\n".join(
                    (
                        "One strong idea can become a full week of useful content.",
                        "",
                        "Visual angle: show the original long-form piece becoming channel-specific drafts.",
                        f"Key takeaway: {claim_one}",
                        "Make it useful: pull one audience pain point, one proof point, and one clear action.",
                        "",
                        cta,
                    )
                ),
                500,
                1200,
            )
            insta_tags = _pad_hashtags(tags, ("#contentmarketing", "#contentstrategy", "#marketingops", "#socialcontent", "#repurposing"))[:12]
            drafts.append(
                PlatformDraft(
                    platform="instagram",
                    content_type="caption",
                    hook="One strong idea can become a full week of useful content.",
                    body=body,
                    cta=cta,
                    hashtags=insta_tags[: max(5, min(len(insta_tags), 12))],
                    visual_angle="Carousel: blog cover, key insight, platform adaptations, final CTA.",
                    why_this_works="It gives the reviewer a visual content angle instead of a plain summary.",
                    audience_value=audience_value.why_it_matters,
                    usage_notes="Pair with a carousel or short reel that shows the transformation.",
                    quality_score=88,
                )
            )
        elif strategy.platform == "x_twitter":
            posts = (
                "One good long-form piece should not become five copy-pasted posts.",
                f"Start with the source claim: {truncate_sentence(claim_one, 214)}",
                f"Then translate the value for the audience: {truncate_sentence(audience_value.why_it_matters, 196)}",
                "Each channel needs a different job: insight, visual hook, conversation starter, or quick script.",
                f"CTA: {truncate_sentence(cta, 250)}",
            )
            drafts.append(
                PlatformDraft(
                    platform="x_twitter",
                    content_type="thread",
                    hook=posts[0],
                    body="\n\n".join(f"{i + 1}/{len(posts)} {post}" for i, post in enumerate(posts)),
                    cta=cta,
                    hashtags=tags[:2],
                    thread_posts=posts,
                    why_this_works="The thread turns one source into sequential ideas without repeating the same sentence.",
                    audience_value=audience_value.why_it_matters,
                    usage_notes="Review each post manually before posting; this agent does not publish.",
                    quality_score=87,
                )
            )
        elif strategy.platform == "short_video":
            voiceover = (
                f"Hook: One approved article can do more than sit in the archive. "
                f"Here is the useful idea: {claim_one} "
                f"Now turn it into platform-native content with one insight, one takeaway, and one action. {cta}"
            )
            drafts.append(
                PlatformDraft(
                    platform="short_video",
                    content_type="script",
                    hook="One approved article can do more than sit in the archive.",
                    body="30-60 second short-video script for human review.",
                    cta=cta,
                    scene_directions=(
                        "0-3s: show the article headline and a bold text hook.",
                        "4-20s: highlight the strongest source claim.",
                        "21-45s: show three platform adaptations.",
                        "46-60s: close with the CTA.",
                    ),
                    voiceover=voiceover,
                    on_screen_text=("Approved blog", "Core insight", "Channel-native drafts", "Review before posting"),
                    why_this_works="It includes hook, shot flow, voiceover, on-screen text, and CTA.",
                    audience_value=audience_value.why_it_matters,
                    usage_notes="Use as a draft script only; no video generation or publishing is performed.",
                    quality_score=89,
                )
            )
        elif strategy.platform == "newsletter":
            body = _fit_length(
                f"{parsed.summary}\n\nThe practical reason to read the full piece: {audience_value.why_it_matters}\n\n{cta}",
                250,
                900,
            )
            drafts.append(
                PlatformDraft(
                    platform="newsletter",
                    content_type="email",
                    hook=f"Why this matters: {truncate_sentence(core.main_message, 80)}",
                    body=body,
                    cta=cta,
                    subject_line=truncate_sentence(parsed.title or core.main_message, 70),
                    preview_text=truncate_sentence(audience_value.why_it_matters, 110),
                    why_this_works="It gives a concise click reason and keeps the original article as the anchor.",
                    audience_value=audience_value.why_it_matters,
                    usage_notes="Optional v1 email snippet for review; no email is sent.",
                    quality_score=86,
                )
            )
    return tuple(drafts)


# --- LLM-authored draft coercion -------------------------------------------------------------
# The LLM produces the creative content; these helpers parse it into validated PlatformDrafts,
# apply deterministic structural finishing, and fall back to the template draft per platform
# when the LLM payload is missing or too thin to use. Quality is judged downstream by the
# deterministic validators (so generic LLM content still fails the gate).

_LLM_MIN_HOOK_WORDS = 4
_LLM_MIN_BODY_WORDS = 12
_LLM_MIN_WHY_WORDS = 6


def llm_draft_usable(draft: LLMPlatformDraft) -> bool:
    """Whether an LLM draft is *complete* enough to use (NOT a quality judgement).

    Completeness only — generic/ungrounded/weak content is intentionally allowed through so the
    deterministic quality gate can fail it. Rejecting on quality here would mask a bad LLM with a
    clean template and silently weaken the gate.
    """
    if len(_WORD_RE.findall(draft.hook)) < _LLM_MIN_HOOK_WORDS:
        return False
    if not draft.cta.strip():
        return False
    if len(_WORD_RE.findall(draft.why_this_works)) < _LLM_MIN_WHY_WORDS:
        return False
    if not draft.audience_value.strip():
        return False
    body_words = len(_WORD_RE.findall(draft.body))
    thread_words = len(_WORD_RE.findall(" ".join(draft.thread_posts)))
    voice_words = len(_WORD_RE.findall(draft.voiceover))
    return max(body_words, thread_words, voice_words) >= _LLM_MIN_BODY_WORDS


def _merge_llm_into_draft(
    base: PlatformDraft, llm: LLMPlatformDraft, rule: PlatformRules
) -> PlatformDraft:
    """Build a structurally-valid PlatformDraft from LLM creative content.

    Creative fields (hook, body, cta, why, audience value, visual angle, subject/preview) come from
    the LLM; structural fields the LLM omits or gets wrong are donated by the deterministic
    template ``base`` so the platform validators are never fighting LLM formatting mistakes.
    """
    cta = llm.cta.strip()
    if not cta or cta.lower() in _WEAK_CTAS:
        cta = base.cta

    if llm.hashtags:
        tags = _safe_hashtags(llm.hashtags)
        tags = tags[: rule.max_hashtags]
        if rule.min_hashtags and len(tags) < rule.min_hashtags:
            tags = base.hashtags
    else:
        tags = base.hashtags

    thread_posts = base.thread_posts
    if base.platform == "x_twitter" and llm.thread_posts:
        candidate = tuple(truncate_sentence(p, 280) for p in llm.thread_posts if p.strip())
        if (
            rule.min_thread_posts <= len(candidate) <= rule.max_thread_posts
            and not repeated_sentence_starts(candidate)
        ):
            thread_posts = candidate

    scene = llm.scene_directions if (base.platform == "short_video" and llm.scene_directions) else base.scene_directions
    voiceover = llm.voiceover.strip() if (base.platform == "short_video" and llm.voiceover.strip()) else base.voiceover
    on_screen = llm.on_screen_text if (base.platform == "short_video" and llm.on_screen_text) else base.on_screen_text

    if base.platform == "x_twitter":
        body = "\n\n".join(f"{i + 1}/{len(thread_posts)} {post}" for i, post in enumerate(thread_posts)) if thread_posts else base.body
    elif rule.max_chars:
        body = _fit_length(llm.body, rule.min_chars, rule.max_chars)
    else:
        body = llm.body.strip() or base.body

    draft = base.validated_copy(
        hook=llm.hook.strip(),
        body=body,
        cta=cta,
        hashtags=tags,
        thread_posts=thread_posts,
        scene_directions=scene,
        voiceover=voiceover,
        on_screen_text=on_screen,
        visual_angle=llm.visual_angle.strip() or base.visual_angle,
        subject_line=llm.subject_line.strip() or base.subject_line,
        preview_text=llm.preview_text.strip() or base.preview_text,
        why_this_works=llm.why_this_works.strip() or base.why_this_works,
        audience_value=llm.audience_value.strip() or base.audience_value,
    )
    return trim_to_platform_limit(draft, rule)


def coerce_llm_drafts(
    request: Agent02Request,
    parsed: ParsedSource,
    core: CoreMessage,
    audience_value: AudienceValue,
    strategies: tuple[PlatformStrategy, ...],
    bundle: LLMDraftBundle,
    *,
    base_drafts: tuple[PlatformDraft, ...] | None = None,
) -> tuple[tuple[PlatformDraft, ...], int]:
    """Convert an LLM draft bundle into validated PlatformDrafts.

    Returns ``(drafts, used)`` where ``used`` is the number of platforms whose draft came from the
    LLM. Platforms with no usable LLM draft fall back to the deterministic ``base_drafts`` (fresh
    templates for generation, the current drafts for a revision). ``used == 0`` means a full
    deterministic fallback occurred.
    """
    if base_drafts is None:
        base_drafts = make_platform_drafts(request, parsed, core, audience_value, strategies)
    base_by_platform = {d.platform: d for d in base_drafts}
    llm_by_platform = {d.platform: d for d in bundle.drafts}
    rules_by_platform = {r.platform: r for r in platform_rules(tuple(base_by_platform))}
    out: list[PlatformDraft] = []
    used = 0
    for strategy in strategies:
        base = base_by_platform.get(strategy.platform)
        if base is None:
            continue
        llm = llm_by_platform.get(strategy.platform)
        rule = rules_by_platform.get(strategy.platform)
        if llm is not None and rule is not None and llm_draft_usable(llm):
            out.append(_merge_llm_into_draft(base, llm, rule))
            used += 1
        else:
            out.append(base)
    return tuple(out), used


def validate_platform_draft(draft: PlatformDraft, rule: PlatformRules) -> PlatformValidationResult:
    issues: list[str] = []
    warnings: list[str] = []
    text = draft_text(draft)
    char_count = len(text)
    hashtag_count = len(draft.hashtags)
    score = 100
    if rule.requires_hook and len(_WORD_RE.findall(draft.hook)) < 4:
        issues.append("weak hook")
        score -= 15
    if rule.requires_cta and not draft.cta.strip():
        issues.append("missing CTA")
        score -= 15
    if rule.min_chars and char_count < rule.min_chars:
        issues.append("too short for platform")
        score -= 10
    if (
        rule.max_chars
        and char_count > rule.max_chars
        and not (draft.platform == "x_twitter" and draft.content_type == "thread")
    ):
        issues.append("too long for platform")
        score -= 10
    if hashtag_count < rule.min_hashtags:
        issues.append("too few hashtags")
        score -= 8
    if hashtag_count > rule.max_hashtags:
        issues.append("too many hashtags")
        score -= 8
    if rule.requires_visual_angle and not draft.visual_angle.strip():
        issues.append("missing visual/content angle")
        score -= 15
    if draft.platform == "x_twitter":
        if draft.content_type == "post" and len(draft.body) > 280:
            issues.append("single X/Twitter post exceeds 280 characters")
            score -= 25
        if draft.content_type == "thread":
            if not (rule.min_thread_posts <= len(draft.thread_posts) <= rule.max_thread_posts):
                issues.append("thread must have 4-7 posts")
                score -= 15
            if any(len(post) > 280 for post in draft.thread_posts):
                issues.append("thread post exceeds 280 characters")
                score -= 15
            if repeated_sentence_starts(draft.thread_posts):
                issues.append("thread repeats the same sentence structure")
                score -= 10
    if draft.platform == "short_video":
        if not draft.scene_directions or not draft.voiceover or not draft.on_screen_text:
            issues.append("short video script missing scene, voiceover, or on-screen text")
            score -= 25
    if _GENERIC_RE.search(text):
        warnings.append("generic marketing phrase detected")
        score -= 10
    return PlatformValidationResult(
        platform=draft.platform,
        passed=score >= 75 and not issues,
        score=max(0, score),
        issues=tuple(issues),
        warnings=tuple(warnings),
        character_count=char_count,
        hashtag_count=hashtag_count,
    )


def validate_all_platforms(
    drafts: tuple[PlatformDraft, ...],
    rules: tuple[PlatformRules, ...],
) -> tuple[PlatformValidationResult, ...]:
    by_platform = {rule.platform: rule for rule in rules}
    return tuple(validate_platform_draft(draft, by_platform[draft.platform]) for draft in drafts)


def check_factual_consistency(
    parsed: ParsedSource,
    drafts: tuple[PlatformDraft, ...],
) -> FactualConsistencyReport:
    source_text = " ".join([parsed.body, " ".join(claim.text for claim in parsed.source_claims)]).lower()
    unsupported: list[UnsupportedClaim] = []
    changed_meaning = False
    for draft in drafts:
        text = draft_text(draft)
        if _PUBLISHING_CLAIM_RE.search(text):
            unsupported.append(
                UnsupportedClaim(
                    platform=draft.platform,
                    claim_text="Draft claims content was published, posted, scheduled, or sent.",
                    reason="Agent 02 v1 is draft-only and cannot claim external actions happened.",
                    severity="terminal",
                    code="fake_publishing_claim",
                )
            )
        if _INJECTION_RE.search(text):
            unsupported.append(
                UnsupportedClaim(
                    platform=draft.platform,
                    claim_text="Draft appears to include source instruction text.",
                    reason="Source instructions must be treated as untrusted data.",
                    severity="terminal",
                    code="prompt_injection_followed",
                )
            )
        for sentence in split_sentences(text):
            low = sentence.lower()
            has_stat = _FAKE_STAT_RE.search(sentence) is not None
            claimish = has_stat or _EXTERNAL_PROOF_RE.search(low) is not None
            if claimish and sentence.lower() not in source_text:
                overlap = token_overlap(sentence, source_text)
                if overlap < 0.45:
                    unsupported.append(
                        UnsupportedClaim(
                            platform=draft.platform,
                            claim_text=truncate_sentence(sentence, 140),
                            reason="Claim is not sufficiently grounded in extracted source claims.",
                            severity="terminal" if has_stat else "retriable",
                            code="fake_statistics" if has_stat else "weak_claim_grounding",
                        )
                    )
    if any(item.reason.lower().find("changed meaning") >= 0 for item in unsupported):
        changed_meaning = True
    terminal_count = sum(1 for item in unsupported if item.severity == "terminal")
    score = max(0, 100 - terminal_count * 35 - (len(unsupported) - terminal_count) * 15)
    return FactualConsistencyReport(
        passed=not unsupported and not changed_meaning,
        score=score,
        unsupported_claims=tuple(unsupported),
        changed_meaning=changed_meaning,
    )


def usefulness_review(drafts: tuple[PlatformDraft, ...]) -> UsefulnessReport:
    issues: list[str] = []
    generic = any(_GENERIC_RE.search(draft_text(d)) is not None for d in drafts)
    repeated = cross_platform_similarity(drafts) > 0.82
    if generic:
        issues.append("generic content detected")
    if repeated:
        issues.append("same content reused across platforms with only small changes")
    for draft in drafts:
        if len(_WORD_RE.findall(draft.why_this_works)) < 6:
            issues.append(f"{draft.platform} lacks useful explanation")
        if draft.quality_score < 75:
            issues.append(f"{draft.platform} platform draft below minimum score")
    score = 100 - len(set(issues)) * 12
    return UsefulnessReport(
        passed=score >= 85 and not generic and not repeated,
        score=max(0, score),
        generic_content_detected=generic,
        repeated_across_platforms=repeated,
        issues=tuple(dict.fromkeys(issues)),
    )


def quality_review(
    validations: tuple[PlatformValidationResult, ...],
    factual: FactualConsistencyReport,
    usefulness: UsefulnessReport,
    drafts: tuple[PlatformDraft, ...],
    confidential_flags: tuple[str, ...] = (),
) -> QualityReport:
    hard_fails: list[HardFail] = []
    suggestions: list[str] = []
    if confidential_flags:
        hard_fails.append(
            HardFail(
                code="confidential_content_exposed",
                severity="terminal",
                reason="Source content contains confidential/internal-only markers.",
            )
        )
        suggestions.append("Use only public, approved source material for repurposing.")
    if not factual.passed:
        for item in factual.unsupported_claims:
            hard_fails.append(
                HardFail(
                    code=item.code,
                    severity=item.severity,
                    reason=item.reason,
                    platform=item.platform,
                )
            )
            suggestions.append(f"Ground or remove claim in {item.platform}: {item.claim_text}")
        if factual.changed_meaning:
            hard_fails.append(
                HardFail(
                    code="changed_source_meaning",
                    severity="terminal",
                    reason="Draft appears to change the meaning of the source content.",
                )
            )
    if usefulness.generic_content_detected:
        hard_fails.append(
            HardFail(code="generic_content", severity="retriable", reason="Generic content detected.")
        )
        suggestions.append("Replace generic phrasing with source-specific value.")
    if usefulness.repeated_across_platforms:
        hard_fails.append(
            HardFail(code="same_content_reused", severity="retriable", reason="Drafts are too similar.")
        )
        suggestions.append("Create distinct angles and structures per platform.")
    for result in validations:
        if not result.passed:
            hard_fails.append(
                HardFail(
                    code="platform_mismatch",
                    severity="retriable",
                    reason=", ".join(result.issues) or "Platform validation failed.",
                    platform=result.platform,
                )
            )
            suggestions.append(f"Revise {result.platform} to satisfy platform rules.")
    if any(d.cta.strip().lower() in _WEAK_CTAS for d in drafts):
        hard_fails.append(
            HardFail(code="weak_cta", severity="retriable", reason="CTA is too generic.")
        )
        suggestions.append("Replace weak CTAs with a source-specific next step.")
    platform_scores = tuple(PlatformScore(platform=r.platform, score=r.score) for r in validations)
    platform_fit = min(15, max(0, round((sum(r.score for r in validations) / max(len(validations), 1)) * 0.15)))
    factual_score = min(15, round(factual.score * 0.15))
    usefulness_score = min(15, round(usefulness.score * 0.15))
    hook_score = 10 if all(len(_WORD_RE.findall(d.hook)) >= 4 for d in drafts) else 6
    cta_score = 10 if all(d.cta.strip() and d.cta.strip().lower() not in _WEAK_CTAS for d in drafts) else 5
    audience_score = 14 if all(d.audience_value.strip() for d in drafts) else 8
    clarity_score = 9 if all(len(_WORD_RE.findall(draft_text(d))) >= 25 for d in drafts) else 6
    sub = QualitySubScores(
        audience_relevance=audience_score,
        usefulness=usefulness_score,
        factual_consistency=factual_score,
        platform_fit=platform_fit,
        hook_strength=hook_score,
        message_clarity=clarity_score,
        cta_quality=cta_score,
        brand_tone_alignment=5,
        readability_polish=5,
    )
    overall = (
        sub.audience_relevance
        + sub.usefulness
        + sub.factual_consistency
        + sub.platform_fit
        + sub.hook_strength
        + sub.message_clarity
        + sub.cta_quality
        + sub.brand_tone_alignment
        + sub.readability_polish
    )
    terminal = any(h.severity == "terminal" for h in hard_fails)
    pass_flag = overall >= 85 and not hard_fails and all(p.score >= 75 for p in platform_scores)
    needs_revision = bool(hard_fails) and not terminal
    if not pass_flag and not suggestions:
        suggestions.append("Improve source specificity, platform fit, and CTA clarity.")
    return QualityReport(
        overall_score=overall,
        sub_scores=sub,
        platform_scores=platform_scores,
        hard_fails=tuple(dedupe_hard_fails(hard_fails)),
        pass_flag=pass_flag,
        needs_revision=needs_revision,
        improvement_suggestions=tuple(dict.fromkeys(suggestions)),
    )


def revise_drafts(
    drafts: tuple[PlatformDraft, ...],
    quality: QualityReport,
) -> tuple[PlatformDraft, ...]:
    revised: list[PlatformDraft] = []
    for draft in drafts:
        body = draft.body
        cta = draft.cta
        thread_posts = draft.thread_posts
        voiceover = draft.voiceover
        if any(h.code == "generic_content" for h in quality.hard_fails):
            body = body.replace("One strong idea", "This source-backed idea")
            body = body.replace("Most teams", "Content teams")
        if any(h.code == "weak_cta" for h in quality.hard_fails):
            replacement_cta = "Read the full source before planning your next content move."
            body = body.replace(draft.cta, replacement_cta) if draft.cta else body
            thread_posts = tuple(
                post.replace(draft.cta, replacement_cta) for post in draft.thread_posts
            )
            voiceover = draft.voiceover.replace(draft.cta, replacement_cta)
            cta = replacement_cta
        if any(h.platform == draft.platform and h.code == "platform_mismatch" for h in quality.hard_fails):
            body = body + "\n\nReviewer note: tighten the channel format before publishing manually."
        revised.append(
            draft.validated_copy(
                body=body,
                cta=cta,
                thread_posts=thread_posts,
                voiceover=voiceover,
                why_this_works=(draft.why_this_works or "Revised for clearer platform fit."),
                quality_score=max(draft.quality_score, 82),
            )
        )
    return tuple(revised)


def hard_fail_status(quality: QualityReport | None) -> str | None:
    if quality is None:
        return None
    if any(h.severity == "terminal" for h in quality.hard_fails):
        return "needs_human"
    if quality.pass_flag:
        return "pass"
    if quality.needs_revision:
        return "revise"
    return "needs_human"


def build_markdown_package(
    source_title: str,
    drafts: tuple[PlatformDraft, ...],
    quality: QualityReport | None,
    notes: str = "",
) -> str:
    lines = [f"# Repurposed Content Package: {source_title or 'Untitled Source'}", ""]
    if quality:
        lines.append(f"Quality score: {quality.overall_score}/100")
        lines.append("")
    if notes:
        lines.append(f"Notes: {notes}")
        lines.append("")
    for draft in drafts:
        lines.append(f"## {display_platform(draft.platform)}")
        if draft.subject_line:
            lines.append(f"Subject: {draft.subject_line}")
        if draft.preview_text:
            lines.append(f"Preview: {draft.preview_text}")
        if draft.hook:
            lines.append(f"Hook: {draft.hook}")
        if draft.thread_posts:
            lines.extend(f"{idx + 1}. {post}" for idx, post in enumerate(draft.thread_posts))
        elif draft.scene_directions:
            lines.append("Scene flow:")
            lines.extend(f"- {item}" for item in draft.scene_directions)
            lines.append(f"Voiceover: {draft.voiceover}")
            if draft.on_screen_text:
                lines.append("On-screen text: " + ", ".join(draft.on_screen_text))
        else:
            lines.append(draft.body)
        if draft.hashtags:
            lines.append("Hashtags: " + " ".join(draft.hashtags))
        if draft.cta:
            lines.append("CTA: " + draft.cta)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def hashtag_sets(drafts: tuple[PlatformDraft, ...]) -> tuple[HashtagSet, ...]:
    return tuple(HashtagSet(platform=d.platform, hashtags=d.hashtags) for d in drafts if d.hashtags)


def cta_options(request: Agent02Request) -> tuple[str, ...]:
    cta = request.cta.strip() or "Read the full piece and review the next step."
    return (
        cta,
        "Use this idea in your next content planning session.",
        "Save the full article for deeper review.",
    )


def draft_text(draft: PlatformDraft) -> str:
    return " ".join(
        part
        for part in (
            draft.hook,
            draft.body,
            draft.cta,
            " ".join(draft.thread_posts),
            " ".join(draft.scene_directions),
            draft.voiceover,
            " ".join(draft.on_screen_text),
            draft.visual_angle,
            draft.subject_line,
            draft.preview_text,
        )
        if part
    )


def cross_platform_similarity(drafts: tuple[PlatformDraft, ...]) -> float:
    texts = [draft_text(d) for d in drafts if draft_text(d)]
    if len(texts) < 2:
        return 0.0
    scores: list[float] = []
    for idx, left in enumerate(texts):
        for right in texts[idx + 1 :]:
            scores.append(SequenceMatcher(None, left.lower(), right.lower()).ratio())
    return max(scores) if scores else 0.0


def token_overlap(sentence: str, source_text: str) -> float:
    source_words = set(_WORD_RE.findall(source_text.lower()))
    sent_words = set(_WORD_RE.findall(sentence.lower()))
    if not sent_words:
        return 0.0
    return len(sent_words & source_words) / len(sent_words)


def repeated_sentence_starts(posts: Iterable[str]) -> bool:
    starts = [" ".join(_WORD_RE.findall(post.lower())[:3]) for post in posts]
    starts = [s for s in starts if s]
    return len(starts) != len(set(starts))


def first_sentence(text: str) -> str:
    sentences = split_sentences(text)
    return sentences[0] if sentences else first_words(text, 20)


def first_words(text: str, count: int) -> str:
    words = _WORD_RE.findall(text)
    return " ".join(words[:count])


def truncate_sentence(text: str, limit: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;:.") + "."


def trim_to_platform_limit(draft: PlatformDraft, rule: PlatformRules) -> PlatformDraft:
    if (
        not rule.max_chars
        or not draft.body
        or (draft.platform == "x_twitter" and draft.content_type == "thread")
        or len(draft_text(draft)) <= rule.max_chars
    ):
        return draft

    body = draft.body
    for _ in range(3):
        excess = len(draft_text(draft.validated_copy(body=body))) - rule.max_chars
        if excess <= 0:
            break
        body_limit = max(rule.min_chars, len(body) - excess - 12)
        if body_limit >= len(body):
            body_limit = max(0, len(body) - excess - 12)
        body = truncate_sentence(body, body_limit)
    return draft.validated_copy(body=body)


def display_platform(platform: Platform) -> str:
    return {
        "linkedin": "LinkedIn",
        "instagram": "Instagram",
        "x_twitter": "X/Twitter",
        "short_video": "Short-video script",
        "newsletter": "Newsletter/email",
    }[platform]


def dedupe_hard_fails(items: list[HardFail]) -> tuple[HardFail, ...]:
    seen: set[tuple[str, str, str | None]] = set()
    out: list[HardFail] = []
    for item in items:
        key = (item.code, item.reason, item.platform)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return tuple(out)


def _safe_hashtags(values: tuple[str, ...]) -> tuple[str, ...]:
    tags: list[str] = []
    for value in values:
        token = re.sub(r"[^A-Za-z0-9_]", "", value.strip().replace("#", "").replace(" ", ""))
        if token:
            tags.append("#" + token[:40])
    if not tags:
        tags = ["#content", "#marketing", "#strategy"]
    return tuple(dict.fromkeys(tags))


def _pad_hashtags(tags: tuple[str, ...], extras: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(tags + extras))


def _fit_length(text: str, minimum: int, maximum: int) -> str:
    cleaned = text.strip()
    if len(cleaned) > maximum:
        return cleaned[:maximum].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    if len(cleaned) < minimum:
        filler = (
            "\n\nUse this as a review draft: keep the source claim intact, adjust examples for "
            "the brand, and remove anything that is not supported by the original article."
        )
        while len(cleaned) < minimum:
            cleaned += filler
    if len(cleaned) > maximum:
        cleaned = cleaned[:maximum].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    return cleaned
