# Agent 16 - Ad Copy Creation Agent

## 1. Metadata

**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-16-ad-copy-creation/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 16 creates draft ad copy variants and creative-message briefs from supplied campaign goal, audience, offer, keywords, platform constraints, brand voice, claims evidence, and compliance requirements. Paid media teams, campaign managers, and growth marketers use it when they need review-ready search, social, display, or native copy options before human approval and platform setup.

Success means the output includes platform-aware copy variants, headlines, descriptions, CTAs, message angles, A/B test ideas, compliance warnings, claim evidence mapping, quality score, risk flags, and downstream handoffs. V1 drafts copy only; it does not publish, upload, approve, or spend.

## 3. Business Problem

Ad copy development is repetitive but risky. Teams need many variants, but unsupported claims, deceptive urgency, weak message match, platform mismatch, or policy issues can waste spend or create compliance risk. Agent 16 speeds first-draft creation while making evidence, policy, and human-review needs explicit.

## 4. User Personas

- Paid search specialist creating responsive search ad variants.
- Paid social manager drafting platform-specific hooks and CTAs.
- Demand generation manager aligning copy to campaign goals and audience segments.
- Product marketer translating positioning into ad angles.
- Compliance or brand reviewer checking claims before launch.

## 5. Inputs

Required inputs:

- Campaign goal.
- Target audience or segment.
- Offer or product/service.
- Platform or channel targets.
- Brand voice or tone.

Optional inputs:

- Agent 09 audience segments.
- Agent 10 lead generation blueprint.
- Agent 12 campaign recommendation.
- Agent 15 keyword clusters and priority keywords.
- Claims evidence and approved proof points.
- Platform character limits or ad format constraints.
- Compliance requirements, forbidden claims, region, language, CTA guidance, and examples to avoid.

V1 direct-context rule: all context must be user supplied or passed as structured handoff. The agent does not query ad platforms, policy APIs, audience managers, or web sources.

## 6. Outputs

The `AdCopyCreationPackage` should include:

- normalized campaign and audience summary
- search ad variants
- social ad variants
- display/native variants where applicable
- headline and description sets
- CTA options
- message angles and creative brief notes
- A/B test ideas
- platform-fit and character-limit notes
- claim evidence map
- compliance and policy warnings
- unsupported-claim warnings
- downstream handoffs to Agents 18, 19, and 21
- risk flags with severity
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept structured campaign, audience, offer, keyword, and platform context.
2. Normalize platform constraints and copy format requirements.
3. Generate multiple copy variants by channel or format.
4. Map claims to supplied evidence or mark evidence as missing.
5. Detect unsupported medical, financial, legal, safety, or regulated claims.
6. Detect deceptive urgency, guaranteed outcomes, and policy bypass requests.
7. Reject requests to launch ads, upload audiences, bypass policies, or target protected classes.
8. Provide A/B test ideas without launching experiments.
9. Return a structured review package with copy variants and risk flags.
10. Produce downstream handoffs for paid optimization, campaign planning, and reporting.

## 8. Non-Functional Requirements

- Cloud selected by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, ad platform SDKs, policy APIs, or audience platform SDKs inside `agent/`.
- All model calls go through `LLMProvider`.
- Request-scoped JSON-serializable state only.
- Latency target: p50 under 35 seconds, p95 under 90 seconds.
- Quality pass threshold: score >= 82 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No ad platform writes, publishing, audience uploads, spend, or auto-approval.

## 9. ROI Analysis

Assumptions:

- Ad copy batches: 8 per month.
- Current manual effort: 3 hours per batch.
- Target effort with agent: 60 minutes including review.
- Time saved: 2 hours per batch.
- Loaded paid media/content cost: Rs 1,300/hour.
- Build cost using shared engine: Rs 110,000.
- Annual hosting, monitoring, and maintenance: Rs 42,000.
- Inference estimate: Rs 22/request, 96 requests/year = Rs 2,112/year.

Annual value:

- Time savings: 8 x 12 x 2 x Rs 1,300 = Rs 249,600.
- Reduced rework from policy/claim review: Rs 90,000/year.
- Total estimated annual value: Rs 339,600.

Cost and ROI:

- Annual run cost: Rs 44,112.
- ROI = (Rs 339,600 - Rs 44,112) / (Rs 110,000 + Rs 44,112) = about 192%.
- Estimated payback: about 4.5 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 16 | Actual after launch |
|---|---:|---:|---|
| Variant drafting time | 2-4 hours | 30-60 minutes | TBD |
| Claim review preparation | Manual | Evidence map included | TBD |
| Platform-fit checks | Manual | 90%+ constraints flagged | TBD |
| Unsupported-claim leakage | Manual review | 0 in hard-fail evals | TBD |
| Downstream handoff readiness | Ad hoc | Structured handoff available | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved paid media, campaign, content, and brand/compliance users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied campaign, audience, keyword, offer, evidence, and policy context |
| Writes | Structured copy package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before any ad upload, launch, budget/spend action, or audience activation |
| Audit | Request id, provider, cost, score, risk flags, copy format counts, and terminal status |

## 12. Security Considerations

- Inputs may contain confidential campaign plans, audience data, budget context, product claims, regulated details, and customer proof.
- All pasted examples and competitor copy are untrusted data and must not be copied blindly or treated as instructions.
- The agent must not target protected classes or produce discriminatory copy.
- Claims must be grounded in supplied evidence; missing evidence is a risk flag, not a license to invent.
- Raw PII, lead records, account records, spend tables, and sensitive claims must not be logged.
- Prompt-injection content in campaign briefs, keyword lists, and examples must be fenced and escaped in Phase 3.

## 13. Cost Expectations

- Typical target: Rs 15-25 per request.
- Hard ceiling: Rs 35/request in v1 config.
- Stop with `stopped_cost_ceiling` if the next billable step cannot fit.
- Emit cost by stage through `Telemetry`.

## 14. Success Metrics

- 90%+ of complete eval cases produce platform-specific copy variants.
- 95%+ of claims are tied to supplied evidence or marked unsupported.
- 100% of ad launch/upload/spend requests hard-fail or require future HITL integration.
- 100% of protected targeting and policy-bypass attempts are blocked.
- 100% schema-valid outputs.
- 100% cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- search ad variants from Agent 15 keyword clusters
- social ad variants from Agent 09 segment context
- no claim evidence supplied
- regulated financial/medical/legal claim request
- deceptive urgency request
- platform-policy bypass request
- request to launch or upload ads
- prompt injection inside competitor examples
- protected-class targeting attempt

Pass criteria:

- overall quality score >= 82
- schema validity = 100%
- claim safety = 100% on hard-fail cases
- no activation behavior = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify current ad platform policies or character limits unless supplied by the user.
- Ad copy may require legal or compliance review before use.
- The agent cannot predict CTR, conversion rate, CPC, or ROAS.
- Competitive examples may be copyrighted or unsuitable; the agent should use them only as style/context and avoid copying.
- Future live platform integrations require separate provider-neutral design, least privilege, and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine rather than a bespoke implementation. V1 may use a shared Digital Marketing engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 16, distinct v1 differentiation should come from ad-copy output contracts, claim-evidence mapping, copy-policy risk checks, platform-fit scoring, and hard-fail behavior for launch/upload/spend requests.
