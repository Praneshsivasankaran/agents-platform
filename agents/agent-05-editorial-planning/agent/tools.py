"""Deterministic local helper tools for Agent 05.

These helpers do not call networks, cloud SDKs, search engines, analytics,
calendar APIs, social APIs, CMS APIs, or media generators.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from .schemas import CalendarSlot, PostingFrequency


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def split_text_items(value: object) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        raw = value.replace("\n", ",").replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set, frozenset)):
        raw = tuple(value)
    else:
        raw = (value,)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = clean_text(item)
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


def normalize_platforms(value: object) -> tuple[str, ...]:
    aliases = {
        "li": "linkedin",
        "linkedin post": "linkedin",
        "blog post": "blog",
        "newsletter": "email",
        "email newsletter": "email",
        "x": "twitter",
        "twitter/x": "twitter",
    }
    platforms: list[str] = []
    seen: set[str] = set()
    for item in split_text_items(value):
        key = item.lower().strip()
        normalized = aliases.get(key, key).replace("_", "-")
        normalized = re.sub(r"[^a-z0-9 -]+", "", normalized).strip()
        normalized = re.sub(r"\s+", "-", normalized)
        if normalized and normalized not in seen:
            platforms.append(normalized)
            seen.add(normalized)
    return tuple(platforms)


def parse_date(value: object) -> date:
    text = clean_text(value)
    if not _DATE_RE.match(text):
        raise ValueError("date must use YYYY-MM-DD")
    return date.fromisoformat(text)


def validate_date_range(start: object, end: object) -> tuple[str, ...]:
    errors: list[str] = []
    try:
        start_date = parse_date(start)
        end_date = parse_date(end)
    except ValueError as exc:
        return (str(exc),)
    if end_date < start_date:
        errors.append("date range end must be on or after start")
    if (end_date - start_date).days > 366:
        errors.append("date range must be 366 days or less for v1")
    return tuple(errors)


def days_in_range(start: str, end: str) -> int:
    return (parse_date(end) - parse_date(start)).days + 1


def _month_count(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def planned_post_count(start: str, end: str, frequency: PostingFrequency) -> int:
    start_date = parse_date(start)
    end_date = parse_date(end)
    if frequency.total_posts > 0:
        return frequency.total_posts
    if frequency.cadence == "daily":
        return days_in_range(start, end)
    if frequency.cadence == "monthly":
        return max(1, _month_count(start_date, end_date) * max(1, frequency.count_per_month))
    if frequency.cadence == "custom":
        return max(1, frequency.count_per_week or frequency.count_per_month or 1)
    weeks = max(1, ((end_date - start_date).days // 7) + 1)
    return max(1, weeks * max(1, frequency.count_per_week))


def expand_posting_frequency(
    *,
    start: str,
    end: str,
    frequency: PostingFrequency,
    platforms: tuple[str, ...],
    pillars: tuple[str, ...],
) -> tuple[CalendarSlot, ...]:
    start_date = parse_date(start)
    end_date = parse_date(end)
    if end_date < start_date:
        return ()
    count = min(365, planned_post_count(start, end, frequency))
    total_days = max(1, (end_date - start_date).days + 1)
    slots: list[CalendarSlot] = []
    for index in range(count):
        offset = 0 if count == 1 else round(index * (total_days - 1) / max(1, count - 1))
        planned = start_date + timedelta(days=offset)
        platform = platforms[index % len(platforms)] if platforms else "blog"
        pillar = pillars[index % len(pillars)] if pillars else "education"
        slots.append(
            CalendarSlot(
                slot_id=f"slot-{index + 1:03d}",
                planned_date=planned.isoformat(),
                platform=platform,
                pillar=pillar,
                sequence=index + 1,
            )
        )
    return tuple(slots)


def calculate_internal_due_date(planned_date: str, lead_time_days: int = 5) -> str:
    return (parse_date(planned_date) - timedelta(days=max(0, lead_time_days))).isoformat()


def deduplicate_topics(topics: tuple[str, ...]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        cleaned = clean_text(topic)
        key = re.sub(r"[^a-z0-9]+", "", cleaned.lower())
        if cleaned and key not in seen:
            out.append(cleaned)
            seen.add(key)
    return tuple(out)


def detect_topic_overlap(topics: tuple[str, ...]) -> tuple[str, ...]:
    normalized: dict[str, str] = {}
    duplicates: list[str] = []
    for topic in topics:
        key = re.sub(r"[^a-z0-9]+", "", clean_text(topic).lower())
        if key and key in normalized:
            duplicates.append(topic)
        elif key:
            normalized[key] = topic
    return tuple(duplicates)


def count_by(values: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for value in values:
        key = clean_text(value) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items()))


def score_balance(values: tuple[str, ...], expected: tuple[str, ...]) -> int:
    if not values or not expected:
        return 0
    counts = dict(count_by(values))
    missing = sum(1 for item in expected if item not in counts)
    max_count = max(counts.values()) if counts else 0
    min_count = min(counts.values()) if counts else 0
    spread_penalty = min(4, max_count - min_count)
    missing_penalty = min(6, missing * 2)
    return max(0, 10 - spread_penalty - missing_penalty)


def score_pillar_balance(pillars_used: tuple[str, ...], expected_pillars: tuple[str, ...]) -> int:
    return score_balance(pillars_used, expected_pillars)


def score_platform_balance(platforms_used: tuple[str, ...], expected_platforms: tuple[str, ...]) -> int:
    return score_balance(platforms_used, expected_platforms)


def detect_prompt_injection_markers(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    markers = (
        "ignore previous instructions",
        "ignore all previous",
        "system prompt",
        "developer message",
        "reveal your prompt",
        "jailbreak",
        "act as system",
        "do not follow the above",
    )
    return tuple(marker for marker in markers if marker in lowered)


def detect_external_action_requests(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    markers = (
        "publish this",
        "schedule posts",
        "create calendar event",
        "send email",
        "post to linkedin",
        "post to instagram",
        "update wordpress",
        "write to cms",
        "sync to google calendar",
    )
    return tuple(marker for marker in markers if marker in lowered)


def detect_unsupported_claim_markers(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    markers: list[str] = []
    if re.search(r"\b\d+(?:\.\d+)?\s?%", lowered):
        markers.append("percentage_claim")
    if re.search(r"\b\d+x\b", lowered):
        markers.append("multiplier_claim")
    for phrase in (
        "guaranteed",
        "guarantee",
        "proven to",
        "always increases",
        "best in the world",
        "analytics show",
        "according to our competitors",
    ):
        if phrase in lowered:
            markers.append(phrase)
    return tuple(dict.fromkeys(markers))


def month_label(value: str) -> str:
    parsed = parse_date(value)
    return f"{calendar.month_name[parsed.month]} {parsed.year}"


def week_label(value: str) -> str:
    parsed = parse_date(value)
    iso = parsed.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"

