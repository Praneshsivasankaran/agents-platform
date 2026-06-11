"""MockLLMProvider — deterministic, offline LLMProvider for keyless dev/CI.

Seventh repair pass:
- Updated _SCENARIO_OVERRIDES to match new ExtractedIdeas schema: replaced ideas
  tuple with main_idea (str), key_points (tuple), suggested_angle (str|None).
- Added new BlogPlan fields to overrides: title_candidates, audience, angle,
  target_keywords.

Repair (Increment 3 / Recommendation 1 — intact):
- Removed _extract_scenario and _SCENARIO_RE: scenario selection from message
  content markers is REMOVED.  Scenario is controlled exclusively via the
  default_scenario constructor argument.  User text containing __scenario:X__
  markers no longer affects mock behaviour.
- Updated _SCENARIO_OVERRIDES for 9-dimension SubScores (Issue #1).
  sub_scores dict + consistent overall_score/pass_flag/needs_human per scenario.
"""
from __future__ import annotations
import math
import types
import typing
from typing import Any
from pydantic import BaseModel
from ...interfaces import LLMProvider, LLMResponse, Tier, Usage, validate_structured_schema
from ...interfaces.base import (
    FieldConstraints,
    annotation_can_terminate,
    constraints_allow_value,
    merge_field_constraints,
    normalize_field_constraints,
)


# ── Constraint-aware placeholder generation ───────────────────────────────

def _placeholder(
    annotation: Any,
    c: FieldConstraints | None = None,
    stack: frozenset = frozenset(),
) -> Any:
    c = c or FieldConstraints()
    if getattr(annotation, "__metadata__", None) is not None:
        annotated = normalize_field_constraints(annotation.__metadata__, path="mock.annotated")
        return _placeholder(
            typing.get_args(annotation)[0],
            merge_field_constraints(c, annotated, path="mock.annotated"),
            stack,
        )
    if annotation is str:
        # Ninth repair: use max(1, ...) so unconstrained str fields never produce "" —
        # an empty string fails non-blank validators even when min_length is not declared.
        target = max(1, c.min_length or 0)
        if c.max_length == 0:
            target = 0
        return "x" * target
    if annotation is bytes:
        target = max(1, c.min_length or 0)
        if c.max_length == 0:
            target = 0
        return b"x" * target
    if annotation is bool:
        return False
    if annotation is int:
        lo = (
            math.floor(c.lower) + 1
            if c.lower is not None and c.lower_exclusive
            else math.ceil(c.lower)
            if c.lower is not None
            else None
        )
        hi = (
            math.ceil(c.upper) - 1
            if c.upper is not None and c.upper_exclusive
            else math.floor(c.upper)
            if c.upper is not None
            else None
        )
        value = lo if lo is not None else min(0, hi) if hi is not None else 0
        if not constraints_allow_value(value, c):
            raise ValueError(f"mock: no integer placeholder satisfies constraints {c!r}")
        return value
    if annotation is float:
        candidates = [0.0]
        if c.lower is not None:
            candidates.append(
                math.nextafter(float(c.lower), math.inf)
                if c.lower_exclusive
                else float(c.lower)
            )
        if c.upper is not None:
            candidates.append(
                math.nextafter(float(c.upper), -math.inf)
                if c.upper_exclusive
                else float(c.upper)
            )
        for value in candidates:
            if constraints_allow_value(value, c):
                return value
        raise ValueError(f"mock: no float placeholder satisfies constraints {c!r}")
    if annotation is type(None):
        return None
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Literal:
        for value in args:
            if constraints_allow_value(value, c):
                return value
        raise ValueError(f"mock: no Literal member satisfies constraints {c!r}")
    if origin is typing.Union or origin is getattr(types, "UnionType", type(None)):
        # Deterministically select a finite, constructible branch (never recurse forever).
        # Prefer None when permitted, then the first branch that terminates given the current
        # construction stack (so e.g. Self | str picks str, not the recursive Self branch).
        if type(None) in args:
            return None
        for a in args:
            if annotation_can_terminate(a, stack, c.min_length or 0):
                try:
                    candidate = _placeholder(a, c, stack)
                except ValueError:
                    continue
                if constraints_allow_value(candidate, c):
                    return candidate
        raise ValueError(
            f"mock: union {annotation!r} has no constructible constraint-valid branch "
            f"given stack {{{', '.join(sorted(m.__name__ for m in stack))}}}"
        )
    if origin is tuple:
        if not args:
            return ()
        if len(args) == 2 and args[1] is Ellipsis:
            min_len = c.min_length or 0
            return tuple(_placeholder(args[0], None, stack) for _ in range(min_len))
        return tuple(_placeholder(a, None, stack) for a in args)
    if origin is list:
        return [_placeholder(args[0], None, stack) for _ in range(c.min_length or 0)]
    if origin is dict:
        return {}
    if origin in (set, frozenset):
        return []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _mock_data(annotation, stack)
    return None


def _mock_data(schema: type[BaseModel], stack: frozenset = frozenset()) -> dict[str, Any]:
    # Cycle guard: fail clearly before unbounded recursion (validate_structured_schema rejects
    # impossible schemas pre-call, so this is defense-in-depth for any value that slips through).
    if schema in stack:
        raise ValueError(
            f"mock: recursive cycle constructing {schema.__name__!r} — no terminating path"
        )
    new_stack = stack | {schema}
    result: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if field.is_required():
            constraints = normalize_field_constraints(
                getattr(field, "metadata", ()),
                path=f"{schema.__name__}.{name}",
            )
            result[name] = _placeholder(field.annotation, constraints, new_stack)
    return result


# ── Scenario overrides ────────────────────────────────────────────────────
#
# Overrides for the 9-dimension SubScores design.
# sub_scores dict values must sum to overall_score.
# pass_flag must equal (overall_score >= 80 and not hard_fail_flags).
# needs_human must be True when hard_fail_flags is non-empty.
#
# Pass: sub_scores sum = 88 → overall_score=88 → pass_flag=True
# Revise: sub_scores sum = 62 → overall_score=62 → pass_flag=False
# Needs_human: sub_scores sum = 33 → overall_score=33 → pass_flag=False, hard_fail set

_SCENARIO_OVERRIDES: dict[str, dict[str, Any]] = {
    "pass": {
        # Nine-dimension SubScores that sum to 88 (>= 80 → passes)
        "sub_scores": {
            "structure_flow": 14, "clarity_readability": 13, "idea_coverage": 14,
            "originality": 13, "tone_audience_fit": 9, "seo_usefulness": 8,
            "factual_safety_sources": 9, "grammar_polish": 4, "engagement_value": 4,
        },  # sum = 88
        "overall_score": 88,
        "pass_flag": True,
        "needs_human": False,
        "hard_fail_flags": (),
        "revision_notes": "",
        # ExtractedIdeas — seventh repair: main_idea + key_points replace ideas tuple
        "usable": True,
        "thin_reason": None,
        "main_idea": "Machine learning is transforming healthcare diagnostics.",
        "key_points": (
            "ML models improve diagnosis accuracy over manual methods.",
            "AI reduces time-to-diagnosis in emergency triage settings.",
        ),
        "suggested_angle": "focus on practical applications and near-term clinical impact",
        # BlogPlan — seventh repair: added title_candidates, audience, angle, target_keywords
        "title": "Machine Learning in Healthcare: A New Frontier",
        "title_candidates": (
            "How AI Is Revolutionizing Medical Diagnosis",
            "The Rise of Machine Learning in Clinical Settings",
        ),
        "audience": "technology enthusiasts and healthcare professionals",
        "sections": ("Introduction", "Key Applications", "Challenges", "Conclusion"),
        "tone": "informative",
        "angle": "practical applications and future trends in clinical AI",
        "target_keywords": ("machine learning healthcare", "AI diagnostics", "clinical AI"),
        "key_points": ("ML improves diagnosis accuracy", "Reduces diagnostic time"),
        # BlogEnrichment — overrides for _fallback_enrichment / enrichment stage (AGENT_SPEC §6.4)
        "alternative_titles": ("AI in Medicine: A New Era", "How ML is Changing Healthcare"),
        "short_summary": "Machine learning is transforming healthcare by improving diagnostic accuracy.",
        "seo_keywords": ("machine learning", "healthcare", "AI diagnostics"),
        "suggested_tags": ("ai", "health", "technology"),
        "meta_description": "Discover how machine learning is revolutionizing healthcare diagnostics.",
    },
    "revise": {
        "sub_scores": {
            "structure_flow": 9, "clarity_readability": 10, "idea_coverage": 8,
            "originality": 11, "tone_audience_fit": 6, "seo_usefulness": 5,
            "factual_safety_sources": 7, "grammar_polish": 3, "engagement_value": 3,
        },  # sum = 62
        "overall_score": 62,
        "pass_flag": False,
        "needs_human": False,
        "hard_fail_flags": (),
        "revision_notes": "Needs more depth in the analysis section and a clearer conclusion.",
        # ExtractedIdeas — seventh repair
        "usable": True,
        "thin_reason": None,
        "main_idea": "Machine learning is transforming healthcare diagnostics.",
        "key_points": (
            "ML models improve diagnosis accuracy over manual methods.",
            "AI reduces time-to-diagnosis in emergency triage settings.",
        ),
        "suggested_angle": "focus on practical applications and near-term clinical impact",
        # BlogPlan — seventh repair
        "title": "Machine Learning in Healthcare: A New Frontier",
        "title_candidates": ("How AI Is Revolutionizing Medical Diagnosis",),
        "audience": "technology enthusiasts and healthcare professionals",
        "sections": ("Introduction", "Key Applications", "Challenges", "Conclusion"),
        "tone": "informative",
        "angle": "practical applications and future trends in clinical AI",
        "target_keywords": ("machine learning healthcare", "AI diagnostics"),
        "key_points": ("ML improves diagnosis accuracy", "Reduces diagnostic time"),
    },
    "needs_human": {
        "sub_scores": {
            "structure_flow": 5, "clarity_readability": 4, "idea_coverage": 6,
            "originality": 4, "tone_audience_fit": 3, "seo_usefulness": 3,
            "factual_safety_sources": 4, "grammar_polish": 2, "engagement_value": 2,
        },  # sum = 33
        "overall_score": 33,
        "pass_flag": False,
        "needs_human": True,
        "hard_fail_flags": ("injection_followed",),
        "revision_notes": "Hard fail: apparent prompt injection followed. Escalate to human review.",
        # ExtractedIdeas — seventh repair
        "usable": True,
        "thin_reason": None,
        "main_idea": "Machine learning is transforming healthcare diagnostics.",
        "key_points": (
            "ML models improve diagnosis accuracy over manual methods.",
            "AI reduces time-to-diagnosis in emergency triage settings.",
        ),
        "suggested_angle": None,
        # BlogPlan — seventh repair; angle must be non-blank (eighth repair)
        "title": "Machine Learning in Healthcare: A New Frontier",
        "title_candidates": ("How AI Is Revolutionizing Medical Diagnosis",),
        "audience": "general readers",
        "sections": ("Introduction", "Key Applications", "Challenges", "Conclusion"),
        "tone": "informative",
        "angle": "general healthcare technology overview",
        "target_keywords": ("machine learning", "healthcare"),
        "key_points": ("ML improves diagnosis accuracy", "Reduces diagnostic time"),
    },
    "thin_input": {
        # ExtractedIdeas — seventh repair: main_idea empty (usable=False)
        "usable": False,
        "thin_reason": "Input too thin: fewer than 2 extractable ideas; cannot draft a blog.",
        "main_idea": "",
        "key_points": (),
        "suggested_angle": None,
        # QualityReport (review likely never runs for thin input)
        "sub_scores": {
            "structure_flow": 0, "clarity_readability": 0, "idea_coverage": 0,
            "originality": 0, "tone_audience_fit": 0, "seo_usefulness": 0,
            "factual_safety_sources": 0, "grammar_polish": 0, "engagement_value": 0,
        },
        "overall_score": 0,
        "pass_flag": False,
        "needs_human": True,
        "hard_fail_flags": (),
        "revision_notes": "",
        # BlogPlan — thin_input never reaches plan, but override must be schema-valid
        # in case it is ever instantiated directly (e.g. in tests).
        # Ninth repair: title_candidates and target_keywords now require min_length=1;
        # audience and angle are now required (no default) → must be non-blank.
        "title": "Machine Learning in Healthcare: A New Frontier",
        "title_candidates": ("Thin Input Blog",),
        "audience": "general readers",
        "sections": ("Introduction", "Overview", "Conclusion"),
        "tone": "informative",
        "angle": "general overview",
        "target_keywords": ("blog writing",),
        "key_points": (),
    },
    "retriable_fail": {
        # Nine-dimension SubScores that sum to 51 (< 80 → does not pass)
        # poor_structure flag present → retriable → revision loop
        "sub_scores": {
            "structure_flow": 3, "clarity_readability": 8, "idea_coverage": 10,
            "originality": 8, "tone_audience_fit": 5, "seo_usefulness": 5,
            "factual_safety_sources": 7, "grammar_polish": 3, "engagement_value": 2,
        },  # sum = 51
        "overall_score": 51,
        "pass_flag": False,
        "needs_human": False,
        "hard_fail_flags": ("poor_structure",),
        "revision_notes": "The draft lacks clear section structure; needs reorganization.",
        # ExtractedIdeas — seventh repair
        "usable": True,
        "thin_reason": None,
        "main_idea": "Machine learning is transforming healthcare diagnostics.",
        "key_points": (
            "ML models improve diagnosis accuracy over manual methods.",
            "AI reduces time-to-diagnosis in emergency triage settings.",
        ),
        "suggested_angle": "focus on practical applications",
        # BlogPlan — seventh repair
        "title": "Machine Learning in Healthcare: A New Frontier",
        "title_candidates": ("How AI Is Revolutionizing Medical Diagnosis",),
        "audience": "technology enthusiasts",
        "sections": ("Introduction", "Key Applications", "Challenges", "Conclusion"),
        "tone": "informative",
        "angle": "practical applications",
        "target_keywords": ("machine learning", "healthcare AI"),
        "key_points": ("ML improves diagnosis accuracy", "Reduces diagnostic time"),
    },
    "default": {},
}


def _apply_scenario(
    data: dict[str, Any],
    scenario: str,
    schema: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Apply per-scenario field overrides to a placeholder dict (shallow merge).

    When schema is provided, an override key is applied if it is a declared field
    of the schema — this covers fields with defaults that _mock_data omitted.
    """
    overrides = _SCENARIO_OVERRIDES.get(scenario, {})
    if not overrides:
        return data
    merged = dict(data)
    schema_fields = set(schema.model_fields) if schema is not None else set()
    for key, val in overrides.items():
        if key in merged or key in schema_fields:
            merged[key] = val
    return merged


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    for m in reversed(messages):
        if isinstance(m.get("content"), str):
            return m["content"]
    return ""


def _approx_tokens(messages: list[dict]) -> int:
    chars = sum(len(m["content"]) for m in messages if isinstance(m.get("content"), str))
    return max(1, chars // 4)


class MockLLMProvider(LLMProvider):
    """Deterministic offline provider.

    Scenario selection is controlled ONLY via the default_scenario constructor
    argument.  Message content is never scanned for scenario markers (removed in
    Increment 3 repair to prevent user text from influencing mock behaviour).

    Parameters
    ----------
    default_scenario:
        Scenario name applied to all calls.  Recognised values: "pass", "revise",
        "needs_human", "thin_input", "default".
    """

    name = "mock"

    def __init__(self, default_scenario: str = "default") -> None:
        self._default_scenario = default_scenario

    def respond(
        self,
        messages: list[dict],
        *,
        tier: Tier,
        params: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        response_schema: type | None = None,
    ) -> LLMResponse:
        if response_schema is not None:
            validate_structured_schema(response_schema)

        usage = Usage(prompt_tokens=_approx_tokens(messages), completion_tokens=8, synthetic=True)
        scenario = self._default_scenario

        if response_schema is not None:
            data = _mock_data(response_schema)
            data = _apply_scenario(data, scenario, schema=response_schema)
            return LLMResponse.structured_from(response_schema, data, usage=usage)

        text = f"[mock:{tier}:{scenario}] " + (_last_user_text(messages)[:200] or "response")
        return LLMResponse(text=text, usage=usage)
