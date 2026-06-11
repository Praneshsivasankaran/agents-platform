# ADR-0004: Scaffold-CLI sequencing — manually scaffold Agent 01, extract the `new-agent` CLI afterward

**Date:** 2026-06-05
**Status:** Accepted
**Owner:** _[Human architect]_
**Scope:** Sprint 0 / program-level — the golden agent (Agent 01) and the `new-agent` generator.

> Records the decision to **manually scaffold Agent 01** during its Code phase and to **extract the
> `new-agent` CLI generator from it afterward**, reconciling an apparent conflict with the platform
> lifecycle rule that agents are "generated from the scaffold, never hand-rolled."

---

## Context

The playbook (§2.6, §3.3) and `DESIGN.md` (§14 Cycle 3) state that agents are generated from a
`new-agent` scaffold CLI and never hand-rolled. Agent 01 is the **golden/reference agent**: the first
agent built and the one whose structure every later agent copies.

This creates a sequencing problem: **you cannot generate an agent from a template that does not yet
exist, and you cannot write a faithful template before the reference structure it encodes has been
built and validated.** The `new-agent` CLI is an *output* of getting Agent 01 right, not an input to it.

`DESIGN.md` §18 lists "the `new-agent` generator is available" as a code-phase readiness item, which —
read literally — would require the CLI before Agent 01 begins. That literal reading is what this ADR
corrects.

---

## Decision

1. **Agent 01 is manually scaffolded** during its Code phase (Spiral Cycle 3). Because it is the
   golden/reference agent, its skeleton — `packages/core` interfaces, the per-agent folder layout,
   the node/provider/config/test patterns — is built and validated by hand to *discover and harden*
   the reusable scaffold pattern.
2. **The `new-agent` CLI is extracted after Agent 01 stabilizes** (Spiral Cycle 5 — "fold what was
   painful back into `packages/core` and the scaffold"). It is validated by **regenerating Agent 01's
   own skeleton and diffing** it against the hand-built one.
3. **This does not violate the platform lifecycle.** The "generate, never hand-roll" rule governs
   agents **02–40**, whose structure will already be known. Agent 01 is the sanctioned, one-time
   exception precisely *because* it is the artifact the CLI is derived from. The true code-start
   precondition is "`packages/core` exists," not "the CLI exists."
4. **Future agents (02–40) are generated from the CLI** once it exists; hand-rolling them is not
   permitted.

---

## Consequences

**Locks in / requires:**
- Sprint-0 ordering: `packages/core` interfaces → mocks → import guard / CI → Agent 01 agent logic →
  evals → GCP wiring + Bedrock/Azure stubs → **extract `new-agent` CLI last**.
- `DESIGN.md` §14 / §18 are read as above; `packages/cli/` stays a placeholder until extraction.
- The CLI's first acceptance test is the regenerate-and-diff against Agent 01.

**Accepted trade-offs:**
- Agent 01's skeleton is written before a generator exists, so any later scaffold change must be
  reconciled into both Agent 01 and the generator (mitigated by extracting the CLI *from* Agent 01).

**Follow-on:** none. Orthogonal to ADR-0001 (framework) and ADR-0003 (transcription).

---

## Related

- Reconciles `DESIGN.md` §14 (Spiral) and §18 (code-phase readiness) with playbook §2.6 / §3.3.
- Aligns with the Spiral Planning Method: generalize into the scaffold only after the reference
  agent is proven (Cycle 5).
