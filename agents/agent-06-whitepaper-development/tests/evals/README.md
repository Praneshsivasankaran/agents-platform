# Agent 06 Eval Stubs

These eval fixtures define the first v1 quality gates for the Whitepaper Development Agent.

The implementation tests currently validate that the case file and threshold file are well-formed.
Future eval work should wire these cases into the shared `packages/evals` harness and assert:

- every package is schema-valid
- complete-input cases score at least 80
- prompt injection is not followed
- missing evidence is flagged instead of invented
- every key claim has an evidence status
- generic output cannot pass
- every run stays under the Rs50/request ceiling
