from __future__ import annotations

import json
from pathlib import Path

from core.providers.mock.llm import MockLLMProvider
from core.providers.mock.telemetry import StdoutTelemetry

from agent.service import load_config
from agent.workflow import build_graph


EVAL_DIR = Path(__file__).resolve().parent
_SERVICE = "marketing-operations-eval"


def _load_cases() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((EVAL_DIR / "cases").glob("*.json"))]


def _run(case: dict):
    graph = build_graph(load_config(), MockLLMProvider(default_scenario="pass"), StdoutTelemetry(service=_SERVICE))
    return graph.invoke({"raw_input": case["input"]})["final_output"]


def test_eval_cases() -> None:
    cases = _load_cases()
    assert len(cases) >= 4
    for case in cases:
        package = _run(case)
        expected = case["expected"]
        cid = case["id"]
        if "status" in expected:
            assert package.status == expected["status"], cid
        if "risk_category" in expected:
            assert any(flag.category == expected["risk_category"] for flag in package.risk_flags), cid
        if expected.get("requires_recommendations"):
            assert package.primary_recommendations, cid
        if expected.get("no_recommendations"):
            assert not package.primary_recommendations, cid
        item_types = [rec.item_type.lower() for rec in package.primary_recommendations]
        for needle in expected.get("item_types", ()):
            assert any(needle.lower() in it for it in item_types), f"{cid}: expected {needle!r} in {item_types}"
        section_names = [section.name.lower() for section in package.output_sections]
        for needle in expected.get("section_names", ()):
            assert any(needle.lower() in name for name in section_names), f"{cid}: expected section {needle!r} in {section_names}"
        for term in expected.get("flagged_terms", ()):
            evidence = " ".join((flag.evidence_needed or "") for flag in package.risk_flags).lower()
            assert term.lower() in evidence, f"{cid}: expected flagged term {term!r}"
        if expected.get("redacted_evidence"):
            evidence_text = " ".join(item.claim_supported for item in package.evidence).lower()
            assert "[redacted-" in evidence_text, cid
        for term in expected.get("no_raw_evidence", ()):
            evidence_text = " ".join(item.claim_supported for item in package.evidence).lower()
            assert term.lower() not in evidence_text, cid