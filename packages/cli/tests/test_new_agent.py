"""Tests for the ``new-agent`` scaffold generator (Increment 8 / ADR-0004).

Covers: name + text-input validation; the generated file set; that the generated agent COMPILES,
passes the no-cloud-SDK guard, and runs its own tests green end-to-end on mocks (in an isolated
subprocess that PRESERVES the parent dependency path); the contract surface of the generated agent;
overwrite protection (no --force); and the plan's headline gate — a real bidirectional
regenerate-and-diff against Agent 01, plus drift-regression tests proving the gate fails.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from cli.new_agent import (
    AGENT_01_SPECIALIZATION_FILES,
    GENERIC_STAGE_FILES,
    REUSABLE_SCAFFOLD_FILES,
    generate,
    pascal_case,
    reusable_scaffold_relpaths,
    scaffold_relpaths,
    skeleton_parity_violations,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKAGES = _REPO_ROOT / "packages"
_AGENT_01 = _REPO_ROOT / "agents" / "agent-01-blog-writer"


def _run(cmd: list[str], *, pythonpath: list[Path]) -> subprocess.CompletedProcess:
    """Run a subprocess, PREPENDING our paths to the EXISTING PYTHONPATH.

    Critical: the prepared test runtime may supply pytest and installed deps via PYTHONPATH;
    overwriting it (rather than prepending) drops the path that imports pytest. Preserve it.
    """
    env = dict(os.environ)
    parts = [str(p) for p in pythonpath]
    existing = env.get("PYTHONPATH", "")
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Name + text-input validation
# ---------------------------------------------------------------------------

class TestValidation:
    @pytest.mark.parametrize("slug,expected", [
        ("report-writer", "ReportWriter"), ("blog-writer", "BlogWriter"),
        ("summarizer", "Summarizer"), ("a-b-c", "ABC"),
    ])
    def test_pascal_case(self, slug, expected):
        assert pascal_case(slug) == expected

    @pytest.mark.parametrize("number", ["01", "00", "41", "99", "2", "002", "abc"])
    def test_number_out_of_range_or_malformed_rejected(self, number, tmp_path):
        # 01 is the protected reference; only 02–40 (two-digit) are allowed.
        with pytest.raises(ValueError):
            generate(number, "sample", "Sample Agent", agents_dir=tmp_path)

    @pytest.mark.parametrize("slug", ["Report-Writer", "report_writer", "-leading", "1abc", "a--b"])
    def test_bad_slug_rejected(self, slug, tmp_path):
        with pytest.raises(ValueError):
            generate("02", slug, "Sample Agent", agents_dir=tmp_path)

    @pytest.mark.parametrize("title", [
        "Has\nnewline", "Has\ttab", "Null\x00byte", 'Has"quote', "Back\\slash", "Token@@here", "   ",
    ])
    def test_bad_title_rejected(self, title, tmp_path):
        with pytest.raises(ValueError):
            generate("02", "sample", title, agents_dir=tmp_path)

    @pytest.mark.parametrize("description", ["line\nbreak", 'a"b', "c\\d", "tok@@en", "ctrl\x01"])
    def test_bad_description_rejected(self, description, tmp_path):
        with pytest.raises(ValueError):
            generate("02", "sample", "Sample Agent", description=description, agents_dir=tmp_path)

    def test_blank_description_is_allowed_and_defaulted(self, tmp_path):
        target = generate("02", "sample", "Sample Agent", description="", agents_dir=tmp_path)
        spec = (target / "AGENT_SPEC.md").read_text(encoding="utf-8")
        assert "Sample Agent" in spec  # defaulted from the title, no crash


# ---------------------------------------------------------------------------
# Generated file set + token substitution + accepted-adversarial validity
# ---------------------------------------------------------------------------

class TestGeneratedStructure:
    def test_all_template_files_written(self, tmp_path):
        target = generate("02", "report-writer", "Report Writing Agent", agents_dir=tmp_path)
        assert target.name == "agent-02-report-writer"
        for rel in scaffold_relpaths():
            assert (target / rel).is_file(), f"missing generated file: {rel}"
        # multi-cloud overlays must be present now that they are stable reference overlays
        for overlay in ("config/bedrock.yaml", "config/azure.yaml"):
            assert (target / overlay).is_file()

    def test_tokens_fully_substituted(self, tmp_path):
        target = generate("07", "summarizer", "Summarizer Agent",
                          description="Summarizes things.", agents_dir=tmp_path)
        for path in target.rglob("*"):
            if path.is_file():
                assert "@@" not in path.read_text(encoding="utf-8"), f"unsubstituted token in {path}"

    def test_class_names_use_pascal_prefix(self, tmp_path):
        target = generate("07", "summarizer", "Summarizer Agent", agents_dir=tmp_path)
        assert "class SummarizerPackage(CoreContractModel)" in (target / "agent" / "schemas.py").read_text(encoding="utf-8")
        assert "class SummarizerState(TypedDict" in (target / "agent" / "state.py").read_text(encoding="utf-8")

    def test_accepted_adversarial_inputs_produce_valid_files(self, tmp_path):
        """A tricky-but-accepted title (apostrophe/ampersand/colon/parens) must still yield
        valid Python (compiles) and valid YAML (parses) in every generated file."""
        target = generate("03", "report-writer", "O'Brien & Sons: Reports (v2)",
                          description="Handles O'Brien & Sons' reports — fast.", agents_dir=tmp_path)
        cp = _run([sys.executable, "-W", "error", "-m", "compileall", "-q", str(target)],
                  pythonpath=[_PACKAGES])
        assert cp.returncode == 0, cp.stdout + cp.stderr
        for yml in target.rglob("*.yaml"):
            yaml.safe_load(yml.read_text(encoding="utf-8"))  # raises on malformed YAML

    def test_default_dockerfile_has_no_ffmpeg(self, tmp_path):
        target = generate("02", "sample", "Sample Agent", agents_dir=tmp_path)
        assert "ffmpeg" not in (target / "Dockerfile").read_text(encoding="utf-8")
        base = yaml.safe_load((target / "config" / "base.yaml").read_text(encoding="utf-8"))
        assert "transcription" not in base

    def test_with_media_adds_ffmpeg(self, tmp_path):
        target = generate("02", "sample", "Sample Agent", agents_dir=tmp_path, with_media=True)
        assert "ffmpeg" in (target / "Dockerfile").read_text(encoding="utf-8")
        base = yaml.safe_load((target / "config" / "base.yaml").read_text(encoding="utf-8"))
        assert base["transcription"] == {"provider": "mock", "language": "en"}


# ---------------------------------------------------------------------------
# Overwrite protection (no --force)
# ---------------------------------------------------------------------------

class TestOverwriteProtection:
    def test_existing_target_refused(self, tmp_path):
        generate("02", "sample", "Sample Agent", agents_dir=tmp_path)
        with pytest.raises(FileExistsError):
            generate("02", "sample", "Sample Agent", agents_dir=tmp_path)

    def test_failed_generation_leaves_existing_target_unchanged(self, tmp_path):
        target = generate("02", "sample", "Sample Agent", agents_dir=tmp_path)
        marker = target / "AGENT_SPEC.md"
        original = marker.read_text(encoding="utf-8")
        with pytest.raises(FileExistsError):
            generate("02", "sample", "Different Title", agents_dir=tmp_path)
        assert marker.read_text(encoding="utf-8") == original  # untouched

    def test_agent_01_number_is_protected(self, tmp_path):
        # Even pointed at the real agents dir, number 01 is rejected before any write.
        with pytest.raises(ValueError):
            generate("01", "blog-writer", "Blog Writing Agent", agents_dir=_REPO_ROOT / "agents")

    def test_failed_new_generation_is_atomic(self, tmp_path, monkeypatch):
        original_write_text = Path.write_text
        writes = 0

        def fail_after_first_write(path, *args, **kwargs):
            nonlocal writes
            writes += 1
            if writes > 1:
                raise OSError("intentional write failure")
            return original_write_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_after_first_write)
        with pytest.raises(OSError):
            generate("02", "sample", "Sample Agent", agents_dir=tmp_path)
        assert not (tmp_path / "agent-02-sample").exists()


# ---------------------------------------------------------------------------
# Generated agent is correct: compiles, cloud-neutral, tests pass, contract holds
# ---------------------------------------------------------------------------

class TestGeneratedAgentWorks:
    def test_generated_agent_compiles(self, tmp_path):
        target = generate("02", "sample", "Sample Agent", agents_dir=tmp_path / "agents")
        cp = _run([sys.executable, "-W", "error", "-m", "compileall", "-q", str(target)], pythonpath=[_PACKAGES])
        assert cp.returncode == 0, cp.stdout + cp.stderr

    def test_generated_agent_passes_no_cloud_sdk_guard(self, tmp_path):
        target = generate("02", "sample", "Sample Agent", agents_dir=tmp_path / "agents")
        cp = _run([sys.executable, "-m", "core.checks.no_cloud_sdk", str(target / "agent")], pythonpath=[_PACKAGES])
        assert cp.returncode == 0, cp.stdout + cp.stderr

    def test_generated_agent_tests_pass_offline(self, tmp_path):
        """The generated agent's own tests (ceiling, billing-preservation, trust boundary) pass."""
        target = generate("02", "sample", "Sample Agent", agents_dir=tmp_path / "agents")
        cp = _run([sys.executable, "-m", "pytest", "-o", "addopts=", str(target / "tests"), "-q"],
                  pythonpath=[_PACKAGES, target])
        assert cp.returncode == 0, cp.stdout + cp.stderr

    def test_generated_agent_contract_surface(self, tmp_path):
        """Contract check: the generated agent exposes the same typed contract as the reference."""
        target = generate("02", "sample", "Sample Agent", agents_dir=tmp_path / "agents")
        snippet = (
            "import typing\n"
            "from agent.schemas import StageCost, BillableNodeError\n"
            "import agent.schemas as s, agent.graph as g\n"
            "pkg = next(v for k, v in vars(s).items() if k.endswith('Package') and hasattr(v, 'model_fields'))\n"
            "status_args = set(typing.get_args(pkg.model_fields['status'].annotation))\n"
            "assert status_args == {'pass', 'needs_human', 'stopped_cost_ceiling', 'error'}, status_args\n"
            "tier_args = set(typing.get_args(StageCost.model_fields['tier'].annotation))\n"
            "assert {'cheap', 'strong', 'stt', 'none'} <= tier_args, tier_args\n"
            "assert callable(g.build_graph)\n"
            "assert issubclass(BillableNodeError, Exception)\n"
            "print('contract-ok')\n"
        )
        cp = _run([sys.executable, "-c", snippet], pythonpath=[_PACKAGES, target])
        assert cp.returncode == 0 and "contract-ok" in cp.stdout, cp.stdout + cp.stderr


# ---------------------------------------------------------------------------
# ADR-0004 regenerate-and-diff gate (bidirectional) + drift regression
# ---------------------------------------------------------------------------

class TestRegenerateAgent01Skeleton:
    def _reference_paths(self) -> set[str]:
        # Scan the reference independently. A new reference-only file must be explicitly classified
        # as specialization or the parity gate fails.
        paths: set[str] = set()
        for path in _AGENT_01.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(_AGENT_01).as_posix()
            if rel.endswith(".pyc") or rel.endswith(".gitkeep"):
                continue
            paths.add(rel)
        return paths

    def test_bidirectional_parity_holds(self, tmp_path):
        # Regenerate Agent 01's skeleton shape (number-independent relpaths) and diff both ways.
        target = generate("02", "blog-writer", "Blog Writing Agent", agents_dir=tmp_path)
        generated = {rel for rel in scaffold_relpaths() if (target / rel).exists()}
        violations = skeleton_parity_violations(
            generated, self._reference_paths(),
            reusable=set(reusable_scaffold_relpaths()),
            allowed_generated_specialization=set(GENERIC_STAGE_FILES),
            allowed_reference_specialization=set(AGENT_01_SPECIALIZATION_FILES),
        )
        assert violations == [], "\n".join(violations)

    def test_gate_detects_reverse_drift(self):
        """If the generator stops emitting a reusable scaffold file, the gate must fail."""
        reusable = set(reusable_scaffold_relpaths())
        reference = self._reference_paths()
        dropped = "config/bedrock.yaml"
        generated = set(scaffold_relpaths()) - {dropped}
        violations = skeleton_parity_violations(
            generated,
            reference,
            reusable=reusable,
            allowed_generated_specialization=set(GENERIC_STAGE_FILES),
            allowed_reference_specialization=set(AGENT_01_SPECIALIZATION_FILES),
        )
        assert any("reverse-drift" in v and dropped in v for v in violations), violations

    def test_gate_detects_forward_drift(self):
        """A generated file absent from Agent 01 and not an allowed specialization must fail."""
        reusable = set(reusable_scaffold_relpaths())
        reference = self._reference_paths()
        generated = set(scaffold_relpaths()) | {"agent/nodes/rogue_stage.py"}
        violations = skeleton_parity_violations(
            generated,
            reference,
            reusable=reusable,
            allowed_generated_specialization=set(GENERIC_STAGE_FILES),
            allowed_reference_specialization=set(AGENT_01_SPECIALIZATION_FILES),
        )
        assert any("forward-drift" in v and "rogue_stage" in v for v in violations), violations

    def test_gate_detects_unclassified_reference_drift(self):
        """A new Agent 01 file cannot be invisible merely because the generator lacks it."""
        generated = set(scaffold_relpaths())
        reference = self._reference_paths() | {"agent/new_reusable_contract.py"}
        violations = skeleton_parity_violations(
            generated,
            reference,
            reusable=set(REUSABLE_SCAFFOLD_FILES),
            allowed_generated_specialization=set(GENERIC_STAGE_FILES),
            allowed_reference_specialization=set(AGENT_01_SPECIALIZATION_FILES),
        )
        assert any(
            "reference-drift" in v and "new_reusable_contract.py" in v for v in violations
        ), violations

    def test_only_allowed_specialization_is_the_generic_process_stage(self):
        # Documents the one intended difference between the skeleton and the reference.
        assert GENERIC_STAGE_FILES == {"agent/nodes/process.py"}

    def test_reusable_manifest_is_independent_of_generator_templates(self):
        assert REUSABLE_SCAFFOLD_FILES == reusable_scaffold_relpaths()
        assert REUSABLE_SCAFFOLD_FILES < scaffold_relpaths()
