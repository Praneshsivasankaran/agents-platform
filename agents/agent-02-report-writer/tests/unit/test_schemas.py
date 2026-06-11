"""Unit test: typed I/O contracts (generated skeleton)."""
from __future__ import annotations

import pytest

from agent.schemas import BillableNodeError, CostUsage, StageCost, ReportWriterPackage


def test_package_is_frozen():
    pkg = ReportWriterPackage(status="pass", cost=CostUsage(stage_costs=(), total_inr=0.0))
    with pytest.raises(Exception):
        pkg.status = "error"  # frozen model — assignment must raise


def test_cost_usage_total_must_match_ledger():
    sc = StageCost(stage="process", cost_inr=1.0, tier="cheap")
    with pytest.raises(Exception):
        CostUsage(stage_costs=(sc,), total_inr=2.0)  # total != sum -> ValueError


def test_billable_node_error_carries_stage_cost():
    sc = StageCost(stage="process", cost_inr=1.0, tier="cheap")
    err = BillableNodeError(sc, RuntimeError("boom"))
    assert err.stage_cost is sc
    assert "RuntimeError" in str(err)
