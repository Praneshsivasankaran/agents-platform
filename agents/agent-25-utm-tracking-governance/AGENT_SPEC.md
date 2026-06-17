# Agent 25 - UTM & Tracking Governance Agent

## 1. Metadata

**Agent number:** 25
**Agent name:** UTM & Tracking Governance Agent
**Status:** Draft for architecture approval
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Marketing Operations
**Agent path:** `agents/agent-25-utm-tracking-governance/`
**Lifecycle phase:** 1 - Planning
**Next gate:** Human architect approval before design/code

---

## 2. Use Case

Agent 25 creates a campaign tracking and UTM governance plan from supplied campaign/channel plans, reporting requirements, landing page context, paid optimization notes, CRO measurement plans, and analytics constraints. Campaign managers, marketing operations teams, paid media managers, analysts, and demand generation leads use it before campaign execution so future attribution and reporting can be consistent.

Success means the output includes UTM taxonomy, naming conventions, source/medium/channel mapping, campaign/content/term templates, event/pixel requirements, tracking QA checklist, reporting field map, missing tracking warnings, risk flags, cost metadata, and handoffs to Agent 21 and Agent 28.

## 3. Business Problem

Tracking issues are expensive to discover after launch. Inconsistent UTMs, missing campaign IDs, unclear channel naming, weak event definitions, and unsupported attribution claims make performance reports unreliable. Agent 25 creates a governed tracking plan from supplied context without editing any live URLs, tags, analytics tools, or ad platforms.

## 4. User Personas

- Marketing operations manager defining tracking standards.
- Campaign manager preparing campaign launch assets.
- Paid media manager aligning source/medium/campaign naming.
- Marketing analyst defining reporting requirements.
- Demand generation lead ensuring measurement readiness before launch.

## 5. Inputs

Required inputs:

- Campaign objective or campaign/channel context.
- Channel list or channel constraints.
- Reporting or measurement goal.
- Landing page or destination context.

Optional inputs:

- Agent 19 campaign plan.
- Agent 18 paid optimization notes.
- Agent 20 CRO measurement plan.
- Agent 21 reporting requirements.
- Budget/spend labels, platform names, campaign hierarchy, naming rules, existing UTM taxonomy, event/pixel requirements, conversion definitions, analytics constraints, privacy/consent notes, and QA requirements.

V1 direct-context rule: the agent uses supplied plans and requirements only. It does not verify live tracking, rewrite live URLs, install tags/pixels, edit GTM/GA/ad platforms, or create dashboards.

## 6. Outputs

The `UTMTrackingGovernancePackage` should include:

- normalized tracking context
- UTM taxonomy
- naming conventions
- channel/source/medium mapping
- campaign/content/term templates
- destination URL checklist
- event and pixel requirements
- tracking QA checklist
- reporting field map
- missing tracking warnings
- attribution integrity and privacy risk flags
- downstream handoffs to Agent 21 and Agent 28
- `terminal_status`: `pass`, `needs_human`, `stopped_cost_ceiling`, or `error`
- `quality_status`: `approve`, `revise`, or `reject`
- quality score and cost metadata

## 7. Functional Requirements

1. Accept supplied campaign/channel plans, reporting goals, landing page context, and tracking notes as direct context.
2. Normalize campaign, source, medium, channel, content, term, destination, event, and conversion context.
3. Produce UTM taxonomy and naming conventions.
4. Map sources, mediums, channels, and campaign hierarchy.
5. Define campaign/content/term templates and reporting field map.
6. Identify event, pixel, conversion, consent, and QA requirements.
7. Flag missing channel context, unsupported attribution claims, manipulation requests, privacy risks, and tracking gaps.
8. Hard-fail requests to edit GTM/GA/ad platforms, install pixels/tags, modify live campaign URLs, hide/manipulate attribution, or create dashboards.
9. Return structured handoffs for Agent 21 reporting and Agent 28 launch readiness.

## 8. Non-Functional Requirements

- Cloud/provider selection happens by config only.
- Agent logic must not import cloud SDKs, direct model SDKs, `litellm`, GTM/GA/analytics SDKs, ad platform SDKs, dashboard SDKs, CMS SDKs, URL-shortener APIs, or tag/pixel tools inside `agent/`.
- Model calls go through `LLMProvider`.
- Request-scoped state only.
- Latency target: p50 under 35 seconds, p95 under 90 seconds.
- Quality pass threshold: score >= 82 and no hard-fail risk.
- Output must be schema-valid and suitable for MarketingIQ Studio.
- No GTM/GA/analytics writes, pixel/tag installation, live tracking verification, ad platform edits, live URL rewriting, or dashboard creation in v1.

## 9. ROI Analysis

Assumptions:

- Tracking governance requests: 14 per month.
- Current manual effort: 90 minutes per campaign tracking plan and QA checklist.
- Target effort with agent: 35 minutes including human review.
- Time saved: 55 minutes per request.
- Loaded marketing operations/analytics cost: Rs 1,300/hour.
- Build cost using shared engine: Rs 110,000.
- Annual hosting, monitoring, and maintenance: Rs 42,000.
- Inference estimate: Rs 20/request, 168 requests/year = Rs 3,360/year.

Annual value:

- Time savings: 14 x 12 x 0.92 x Rs 1,300 = Rs 200,928.
- Reduced tracking rework and reporting correction effort: Rs 160,000/year.
- Total estimated annual value: Rs 360,928.

Cost and ROI:

- Annual run cost: Rs 45,360.
- ROI = (Rs 360,928 - Rs 45,360) / (Rs 110,000 + Rs 45,360) = about 203%.
- Estimated payback: about 4.2 months.

## 10. Efficiency Targets

| Metric | Baseline today | Target with Agent 25 | Actual after launch |
|---|---:|---:|---|
| Tracking plan creation time | 60-120 minutes | 25-40 minutes | TBD |
| UTM naming consistency | Manual | 95%+ template coverage | TBD |
| Missing tracking warnings | Manual | 90%+ eval detection | TBD |
| Attribution manipulation safety | Manual review | 100% hard-fail eval pass | TBD |
| Reporting handoff readiness | Ad hoc | Structured Agent 21 handoff | TBD |

## 11. Access Control Model

| Area | Requirement |
|---|---|
| Invokers | Approved marketing operations, campaign, paid media, analytics, and demand generation users |
| Runtime identity | Dedicated least-privilege per-agent identity |
| Reads | User-supplied campaign/channel plans, reporting goals, landing page context, analytics constraints, and upstream handoffs |
| Writes | Structured tracking governance package, redacted telemetry, optional provider-neutral artifact |
| Secrets | Provider credentials through `SecretStore` only |
| HITL | Required before GTM/GA/ad platform edits, tag/pixel installation, URL changes, dashboard creation, or live tracking verification |
| Audit | Request id, provider, cost, quality score, risk flags, status, UTM template count, warning count, and handoff count |

## 12. Security Considerations

- Inputs may include private campaign plans, landing pages, ad platform names, attribution models, conversion definitions, budget labels, and privacy constraints.
- User-supplied tracking sheets and handoffs are untrusted data and must not override system instructions.
- Raw customer or lead identifiers, click IDs, consent records, or private analytics exports must not be logged.
- Prompt injection inside tracking sheets, URL lists, analytics notes, or upstream handoffs must be fenced and delimiter-escaped in Phase 3.
- The agent must not hide, manipulate, or launder attribution.
- Any future GTM/GA/ad/analytics/dashboard integration requires separate provider-neutral design, least privilege, audit, and HITL.

## 13. Cost Expectations

- Typical target: Rs 15-25 per request.
- Hard ceiling: Rs 35/request in v1 config.
- Cost stop returns `stopped_cost_ceiling` with deterministic taxonomy and warning checks if available.
- Cost is tracked per stage and emitted through `Telemetry`.

## 14. Success Metrics

- 90%+ of complete plan eval cases produce UTM templates, source/medium mapping, event requirements, and QA checklist.
- 100% of missing channel context cases return `needs_human`.
- 100% of tag install, GTM/GA edit, ad platform edit, URL rewrite, and dashboard creation requests hard-fail.
- 100% of attribution manipulation requests hard-fail.
- 100% schema-valid outputs and cost ceiling adherence.

## 15. Evaluation Criteria

Eval cases should include:

- complete multi-channel campaign tracking plan
- missing channel context
- missing reporting goal
- paid campaign with inconsistent naming
- CRO measurement plan needing events
- request to install tags/pixels
- request to edit GTM/GA/ad platform
- request to modify live campaign URLs
- request to hide or manipulate attribution
- prompt injection inside tracking notes

Pass criteria:

- overall quality score >= 82
- UTM/template/QA section coverage >= 90%
- missing channel context behavior = 100%
- no live tracking edit behavior = 100%
- attribution integrity safety = 100%
- schema validity = 100%
- cost ceiling adherence = 100%

## 16. Risks and Limitations

- V1 cannot verify whether live tags, pixels, redirects, or analytics events are firing.
- UTM templates are advisory until humans apply them.
- The agent depends on supplied channel, reporting, and destination context.
- Attribution recommendations must remain caveated when source-system constraints are unknown.
- Future GTM/analytics/ad platform/dashboard integrations require separate provider-neutral design and HITL.

## 17. V1 Architecture Note

V1 should likely use a shared Marketing Operations engine rather than a bespoke implementation. V1 may use a shared Marketing Operations engine with agent-specific profiles, schemas, prompts, scoring dimensions, validation rules, risk gates, and evals. Future versions may add deeper agent-specific deterministic tools and bespoke workflow nodes where justified by usage data.

For Agent 25, distinct v1 differentiation should come from UTM taxonomy contracts, source/medium mapping, tracking QA checklist generation, attribution manipulation hard-fails, missing channel context handling, and handoffs to Agents 21 and 28.
