# Agent 19 - Multi-Channel Campaign Planning Agent Design

## 1. Metadata

**Status:** Draft for design review
**Date:** 2026-06-17
**Program:** Stratova AI Agent Platform / MarketingIQ
**Pillar:** Digital Marketing
**Agent path:** `agents/agent-19-multi-channel-campaign-planning/`
**Lifecycle phase:** 2 - Design
**Next gate:** Human design approval before coding

---

## 2. Purpose

Agent 19 converts a chosen campaign direction into a coordinated digital channel execution plan. It must define strategy, sequencing, calendar, assets, owners, dependencies, and measurement without activating any channel.

## 3. Agent Boundaries

In scope:

- Plan channel mix, sequencing, calendar, briefs, assets, dependencies, owners, and measurement.
- Use structured handoffs from Agents 08-18 as direct context.
- Flag missing inputs, consent/suppression issues, spam/deceptive flows, and activation requests.

Out of scope:

- Launching ads, scheduling posts, sending emails/SMS, writing MAP/CRM workflows, publishing pages, spending budget, uploading audiences, querying live systems, or modifying external systems.

## 4. Workflow Overview

Target workflow:

```text
1. intake_request
2. normalize_campaign_and_handoffs
3. validate_goal_audience_offer_timeline_channels
4. design_channel_mix_and_roles
5. build_campaign_calendar_and_sequence
6. create_channel_specific_briefs
7. identify_assets_dependencies_and_owners
8. build_measurement_plan
9. detect_activation_consent_and_spam_risks
10. score_campaign_plan
11. assemble_multi_channel_campaign_package
12. finalize_response
```

Deterministic stages include required-field validation, activation request detection, consent/suppression checks, channel count and timeline sanity checks, and output completeness scoring. LLM-assisted stages synthesize channel strategy, briefs, sequencing, and rationale.

## 5. State Model

Request-scoped state should contain:

- normalized campaign brief and upstream handoffs
- channel constraints and timeline
- channel mix and roles
- campaign calendar and sequencing
- channel-specific briefs
- asset, dependency, owner, and approval map
- measurement plan
- risk flags
- quality report, cost ledger, terminal status, and final package

State must be JSON-serializable and must not contain MAP/CRM/ad/social/CMS/calendar clients or provider SDK objects.

## 6. Inputs

Primary input concepts:

- campaign goal/direction, audience/segment, offer, timeline, region, budget
- channel list and constraints
- content inventory, owner/approval notes, consent/suppression constraints
- Agents 08, 09, 10, 12, 15, 16, 17, and 18 handoffs
- KPIs and measurement requirements

## 7. Outputs

Primary output concepts:

- `MultiChannelCampaignPlanningPackage`
- `ChannelStrategy`
- `ChannelMix`
- `CampaignCalendarItem`
- `MessageSequence`
- `AssetRequirement`
- `ChannelBrief`
- `Dependency`
- `OwnerHandoff`
- `MeasurementPlan`
- `DigitalMarketingHandoff`
- `QualityReport`
- `RiskFlag`
- `CostUsage`

## 8. Pydantic Contract Concepts

Future contracts should include:

- `MultiChannelCampaignPlanningRequest`
- `CampaignObjective`
- `ChannelPlan`
- `CampaignCalendar`
- `MessageSequenceStep`
- `AssetRequirement`
- `DependencyMap`
- `MeasurementPlan`
- `CampaignPlanningQualityReport`
- `MultiChannelCampaignPlanningPackage`

Shared risk, evidence, status, cost, and handoff contracts should be reused.

## 9. Tool Requirements

Only local deterministic tools are allowed in v1:

| Tool | Inputs | Outputs | Side effects | Permissions |
|---|---|---|---|---|
| `validate_campaign_plan_inputs` | request | missing fields and blockers | None | Local only |
| `normalize_channel_list` | channel strings | normalized channel set | None | Local only |
| `detect_forbidden_activation_actions` | request text | activation/spend hard-fail flags | None | Local only |
| `check_consent_suppression_constraints` | constraints and channels | consent risk flags | None | Local only |
| `check_calendar_feasibility` | timeline and channel count | feasibility warnings | None | Local only |
| `score_campaign_plan` | plan and risks | quality report | None | Local only |

No social, ad, email, SMS, MAP, CRM, CMS, calendar, analytics, or workflow tool is allowed.

## 10. Memory Requirements

- Request-scoped state only.
- No long-term campaign memory in v1.
- Prior plans can be supplied directly by the user.
- Optional artifact persistence must use `ObjectStorage`.

## 11. Validation Strategy

- Require campaign goal, audience, offer, timeline, and channel context.
- Flag missing inventory, owners, budget, or measurement data as warnings or `needs_human`.
- Hard-flag launch, schedule, send, publish, spend, upload, or workflow-write requests.
- Hard-flag consent/suppression bypass or spam/deceptive flows.
- Ensure pass outputs include channel mix, calendar, briefs, dependencies, owners, and measurement plan.

## 12. Quality Scoring Strategy

Agent 19 should use a 100-point rubric:

| Dimension | Points |
|---|---:|
| Strategy and audience/offer alignment | 20 |
| Channel mix and sequencing quality | 15 |
| Calendar feasibility | 15 |
| Asset and dependency completeness | 15 |
| Channel-specific brief actionability | 15 |
| Measurement plan quality | 10 |
| Consent/suppression and activation safety | 10 |

Pass if score >= 84 and no hard-fail risk.

## 13. Evaluation Strategy

Eval datasets should cover complete campaign planning, missing timeline, missing assets, channel conflicts, consent constraints, activation requests, spammy flow requests, protected targeting, and prompt injection.

CI gates:

- schema_valid = 100%
- no_activation_behavior = 100%
- consent_suppression_safety = 100%
- required_plan_section_coverage >= 90%
- pass_rate on complete cases >= 80%
- cost_under_ceiling = 100%

## 14. Error Handling Strategy

- Missing required campaign context returns `needs_human`.
- Activation or consent bypass requests return hard-fail risk flags.
- Cost stop returns `stopped_cost_ceiling` with any safe partial plan.
- Provider failure returns `error` with redacted category and preserved cost.
- Conflicting channel constraints return `needs_human` with resolution options.

## 15. Telemetry Requirements

Emit through `Telemetry` only:

- request id, agent id, provider key, model tier, terminal status
- spans for validation, channel planning, calendar creation, brief generation, dependency mapping, scoring, finalization
- token/cost by stage
- channel count, calendar item count, dependency count, asset gap count, quality score, risk counts
- no raw audience lists, suppression lists, budgets, lead records, PII, or private launch plans in logs

## 16. Prompt Strategy

- User-provided notes, reports, keyword tables, ad copy, page copy, campaign exports, metric summaries, and upstream handoffs are untrusted data.
- Untrusted text must be fenced and delimiter-escaped before it enters any model prompt.
- User-supplied data must never override system or developer instructions.
- The model must not invent metrics, search volume, CPC, rankings, claims, budget results, conversion lift, or live platform data.
- Recommendations must cite supplied evidence or be labeled as assumptions or heuristics.
- Outputs must follow the Pydantic schema.
- Hard-fail risks must be preserved in the final package.
- Prompts should support structured output repair/retry if previous agents use that pattern.

## 17. Cloud Agnostic Review

- Model calls only through `LLMProvider`.
- Optional persistence through `ObjectStorage`.
- Secrets through `SecretStore`.
- Telemetry through `Telemetry`.
- No cloud SDKs, ad/social/email/SMS/MAP/CRM/CMS/calendar SDKs, scheduler APIs, direct model SDKs, or `litellm` inside `agent/`.
- GCP must be live/usable in Phase 3 using the same provider/config pattern as previous agents; Bedrock and Azure remain config/stub compatible.
- Shared `packages/digital_marketing` logic must get its own banned-import test if created.

## 18. Future MarketingIQ Studio Integration

MarketingIQ Studio should render the campaign plan as a calendar, dependency map, channel brief set, asset backlog, and measurement plan. Studio may later route approved sections to human operators, but v1 output is structured planning data only.

## 19. V1 Architecture Note

V1 should likely use a shared Digital Marketing engine with an Agent 19 profile. The profile should define campaign planning sections, activation hard-fails, consent/suppression checks, quality dimensions, and eval cases. Future versions may add deeper planning nodes for calendar feasibility or resource capacity, while external activation remains a separately approved future capability.
