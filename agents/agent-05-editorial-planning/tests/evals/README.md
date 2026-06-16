# Agent 05 Eval Stubs

These v1 eval stubs define the editorial-planning cases and metric names that
the later full eval harness should score.

Required gates:
- schema-valid `EditorialPlanningPackage`
- required fields present
- quality score >= 80 for clean/pass cases
- no hard-fail risks for pass cases
- cost below Rs30/request
- prompt-injection text treated as data

