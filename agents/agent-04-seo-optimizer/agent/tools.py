"""Deterministic local helper tools for Agent 04.

These helpers do not call networks, cloud SDKs, search engines, analytics, or
external SEO services. They provide the cheap, auditable checks that should not
need an LLM.
"""
from __future__ import annotations

import re
import unicodedata


_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
_SENTENCE_RE = re.compile(r"[.!?]+")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,3})\s+(.+?)\s*$")


def clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def split_secondary_keywords(value: object) -> tuple[str, ...]:
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


def words(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _WORD_RE.finditer(text or ""))


def count_words(text: str) -> int:
    return len(words(text))


def extract_headings(text: str) -> tuple[str, ...]:
    headings: list[str] = []
    for line in str(text or "").splitlines():
        match = _HEADING_RE.match(line)
        if match:
            headings.append(clean_text(match.group(2).strip("# ")))
    return tuple(headings)


def simple_keyword_presence(text: str, keyword: str) -> bool:
    key = clean_text(keyword).lower()
    return bool(key) and key in str(text or "").lower()


def keyword_density_check(text: str, keyword: str) -> float:
    key = clean_text(keyword).lower()
    if not key:
        return 0.0
    tokens = words(text)
    if not tokens:
        return 0.0
    if " " in key:
        count = str(text or "").lower().count(key)
    else:
        count = sum(1 for token in tokens if token == key)
    return round((count / max(1, len(tokens))) * 100, 3)


def slugify(text: str, *, max_words: int = 9) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    tokens = re.findall(r"[a-z0-9]+", ascii_text.lower())
    if not tokens:
        return "seo-optimized-draft"
    return "-".join(tokens[:max_words])


def _count_syllables(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 0
    groups = re.findall(r"[aeiouy]+", cleaned)
    count = len(groups)
    if cleaned.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def estimate_readability(text: str) -> int:
    token_list = words(text)
    word_count = len(token_list)
    if word_count == 0:
        return 0
    sentence_count = max(1, len([s for s in _SENTENCE_RE.split(text or "") if s.strip()]))
    syllable_count = sum(_count_syllables(token) for token in token_list)
    flesch = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (
        syllable_count / word_count
    )
    return int(max(0, min(100, round(flesch))))


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


def detect_cta_presence(text: str, cta_direction: str = "") -> bool:
    lowered = str(text or "").lower()
    if cta_direction and clean_text(cta_direction).lower() in lowered:
        return True
    cta_markers = (
        "book a demo",
        "schedule",
        "contact us",
        "download",
        "subscribe",
        "try ",
        "start ",
        "audit ",
        "learn more",
        "get started",
    )
    return any(marker in lowered for marker in cta_markers)


def detect_unsupported_claim_markers(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    markers: list[str] = []
    if re.search(r"\b\d+(?:\.\d+)?\s?%", lowered):
        markers.append("percentage_claim")
    if re.search(r"\b\d+x\b", lowered):
        markers.append("multiplier_claim")
    for phrase in ("guaranteed", "guarantee", "proven to", "always increases", "best in the world"):
        if phrase in lowered:
            markers.append(phrase)
    return tuple(dict.fromkeys(markers))


def excessive_repetition(text: str) -> bool:
    token_list = [token for token in words(text) if len(token) > 3]
    if len(token_list) < 40:
        return False
    counts: dict[str, int] = {}
    for token in token_list:
        counts[token] = counts.get(token, 0) + 1
    return any(count / len(token_list) > 0.08 for count in counts.values())


def first_sentence(text: str) -> str:
    cleaned = clean_text(text)
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return parts[0] if parts and parts[0] else cleaned[:180]


def last_sentence(text: str) -> str:
    cleaned = clean_text(text)
    parts = [part for part in re.split(r"(?<=[.!?])\s+", cleaned) if part]
    return parts[-1] if parts else cleaned[-180:]


def top_terms(text: str, *, limit: int = 8) -> tuple[str, ...]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "you",
        "your",
        "into",
        "when",
        "their",
        "will",
        "can",
        "has",
        "have",
        "but",
        "not",
        "they",
        "teams",
    }
    counts: dict[str, int] = {}
    for token in words(text):
        if len(token) > 3 and token not in stop:
            counts[token] = counts.get(token, 0) + 1
    ordered = sorted(counts, key=lambda item: (-counts[item], item))
    return tuple(ordered[:limit])
