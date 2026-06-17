"""Agent-specific Marketing Operations profiles.

The shared workflow stays small and provider-neutral. Profiles carry the
agent-specific scope, required inputs, output sections, risk boundaries, and
quality rubric for Agents 22-28.
"""

from __future__ import annotations

from dataclasses import dataclass


QualityDimension = tuple[str, int]


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    number: int
    slug: str
    title: str
    package_label: str
    purpose: str
    primary_object: str
    required_fields: tuple[str, ...]
    required_any_fields: tuple[tuple[str, ...], ...]
    recommended_outputs: tuple[str, ...]
    output_sections: tuple[str, ...]
    handoff_targets: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    protected_terms: tuple[str, ...]
    unsupported_claim_terms: tuple[str, ...]
    data_caveat_terms: tuple[str, ...]
    quality_dimensions: tuple[QualityDimension, ...]
    pass_threshold: int
    approve_threshold: int
    revise_min_threshold: int
    cost_ceiling_inr: float
    billable_stage: str
    llm_tier: str = "strong"
    metric_mode: str = "operations"


_PROTECTED_TERMS = (
    "age",
    "caste",
    "disability",
    "ethnicity",
    "gender",
    "health status",
    "marital status",
    "pregnancy",
    "race",
    "religion",
    "sexual orientation",
    "veteran status",
)

_COMMON_FORBIDDEN_ACTIONS = (
    "activate",
    "approve campaign",
    "approve launch",
    "automatically approve",
    "bypass approval",
    "bypass compliance",
    "bypass consent",
    "bypass qa",
    "bypass suppression",
    "certify compliance",
    "certify legal",
    "create task",
    "edit crm",
    "edit gtm",
    "edit map",
    "fetch live",
    "install pixel",
    "launch campaign",
    "mark approved",
    "publish",
    "query crm",
    "query analytics",
    "read consent database",
    "schedule launch",
    "send email",
    "send notification",
    "send sms",
    "spend budget",
    "upload audience",
    "write workflow",
)

_UNSUPPORTED_CLAIM_TERMS = (
    "certified compliant",
    "guarantee attribution",
    "guarantee conversions",
    "legally approved",
    "live verified",
    "make up approval",
    "pretend approved",
    "pretend qa passed",
    "prove tracking works",
)


AGENT_22 = AgentProfile(
    agent_id="agent-22",
    number=22,
    slug="campaign-intake-brief-qa",
    title="Campaign Intake & Brief QA Agent",
    package_label="CampaignIntakeBriefQAPackage",
    purpose="Check supplied campaign briefs for completeness, clarity, dependencies, owners, approvals, and readiness.",
    primary_object="campaign intake brief QA package",
    required_fields=("campaign_objective", "target_audience", "offer", "timeline"),
    required_any_fields=(("channels", "workflow_context", "campaign_type"),),
    recommended_outputs=(
        "Normalized campaign brief",
        "Brief completeness score",
        "Missing information warnings",
        "Owner and approval gaps",
        "Dependency and asset gaps",
        "Tracking and measurement gaps",
        "Clarifying questions",
        "Readiness recommendation",
    ),
    output_sections=(
        "normalized_campaign_brief",
        "brief_completeness_score",
        "missing_information_warnings",
        "owner_dependency_approval_gaps",
        "asset_tracking_measurement_gaps",
        "clarifying_questions",
        "readiness_recommendation",
    ),
    handoff_targets=("Agent 23", "Agent 25", "Agent 28"),
    forbidden_actions=("create project", "create jira", "create asana", "create monday task", "update calendar")
    + _COMMON_FORBIDDEN_ACTIONS,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_CLAIM_TERMS,
    data_caveat_terms=("owner", "approval", "launch date", "asset", "tracking", "consent"),
    quality_dimensions=(
        ("brief_context_completeness", 18),
        ("objective_audience_offer_clarity", 15),
        ("timeline_channel_readiness", 12),
        ("owner_dependency_approval_coverage", 15),
        ("asset_tracking_measurement_coverage", 15),
        ("risk_policy_no_activation_handling", 15),
        ("handoff_readiness", 10),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=35.0,
    billable_stage="generate_campaign_intake_qa",
    metric_mode="brief",
)

AGENT_23 = AgentProfile(
    agent_id="agent-23",
    number=23,
    slug="marketing-automation-workflow-design",
    title="Marketing Automation Workflow Design Agent",
    package_label="MarketingAutomationWorkflowDesignPackage",
    purpose="Convert supplied campaign, nurture, routing, and consent context into a human MAP workflow specification.",
    primary_object="marketing automation workflow design package",
    required_fields=("workflow_objective", "trigger_event", "target_audience"),
    required_any_fields=(("offer", "message_sequence", "asset_inventory"), ("consent_context", "compliance_notes")),
    recommended_outputs=(
        "Workflow map",
        "Trigger and entry criteria",
        "Branch logic",
        "Wait steps and cadence",
        "Suppression and exclusion rules",
        "Exit criteria",
        "Field and data dependencies",
        "QA test cases",
        "Rollback and monitoring notes",
    ),
    output_sections=(
        "normalized_workflow_brief",
        "workflow_map",
        "trigger_entry_and_branch_logic",
        "cadence_suppression_and_exit_rules",
        "asset_field_and_data_dependencies",
        "qa_test_cases",
        "rollback_monitoring_and_handoff",
    ),
    handoff_targets=("Agent 28",),
    forbidden_actions=("activate workflow", "create workflow", "import contacts", "update list", "execute webhook", "call api")
    + _COMMON_FORBIDDEN_ACTIONS,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_CLAIM_TERMS,
    data_caveat_terms=("trigger", "branch", "suppression", "exit", "cadence", "consent"),
    quality_dimensions=(
        ("workflow_context_completeness", 15),
        ("trigger_entry_branch_quality", 17),
        ("cadence_suppression_exit_coverage", 18),
        ("asset_field_dependency_readiness", 15),
        ("qa_rollback_monitoring_quality", 15),
        ("consent_safety_no_activation_handling", 15),
        ("handoff_readiness", 5),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=45.0,
    billable_stage="generate_workflow_design",
    metric_mode="workflow",
)

AGENT_24 = AgentProfile(
    agent_id="agent-24",
    number=24,
    slug="crm-map-data-hygiene",
    title="CRM/MAP Data Hygiene Agent",
    package_label="CRMMAPDataHygienePackage",
    purpose="Review supplied CRM/MAP field, mapping, lifecycle, duplicate, and data-quality summaries.",
    primary_object="CRM/MAP data hygiene package",
    required_fields=("system_context", "data_hygiene_objective"),
    required_any_fields=(("field_list", "mapping_notes", "sample_summary", "issue_summary"),),
    recommended_outputs=(
        "Data quality findings",
        "Duplicate and normalization issues",
        "Required field gaps",
        "Field mapping suggestions",
        "Lifecycle inconsistency findings",
        "Validation rule recommendations",
        "Cleanup backlog",
        "Data stewardship notes",
        "PII handling notes",
    ),
    output_sections=(
        "normalized_crm_map_context",
        "data_quality_findings",
        "duplicate_normalization_and_lifecycle_issues",
        "required_field_and_mapping_gaps",
        "validation_rule_recommendations",
        "cleanup_backlog_and_stewardship",
        "pii_redaction_and_limitations",
    ),
    handoff_targets=("Agent 26", "Agent 28"),
    forbidden_actions=(
        "merge records",
        "merge duplicate",
        "delete records",
        "update records",
        "update lifecycle",
        "update field",
        "create field",
        "enrich contacts",
        "export records",
    )
    + _COMMON_FORBIDDEN_ACTIONS,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_CLAIM_TERMS + ("data is clean", "dedupe complete", "verified live crm"),
    data_caveat_terms=("duplicate", "mapping", "lifecycle", "required field", "validation", "sample"),
    quality_dimensions=(
        ("crm_map_context_completeness", 15),
        ("field_mapping_required_gap_detection", 20),
        ("duplicate_normalization_lifecycle_detection", 20),
        ("cleanup_backlog_stewardship_quality", 15),
        ("pii_privacy_redaction_handling", 15),
        ("no_record_mutation_or_query_handling", 10),
        ("handoff_readiness", 5),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=45.0,
    billable_stage="generate_data_hygiene_plan",
    metric_mode="data",
)

AGENT_25 = AgentProfile(
    agent_id="agent-25",
    number=25,
    slug="utm-tracking-governance",
    title="UTM & Tracking Governance Agent",
    package_label="UTMTrackingGovernancePackage",
    purpose="Create a governed tracking and UTM plan from supplied campaign, channel, destination, and reporting context.",
    primary_object="UTM and tracking governance package",
    required_fields=("campaign_objective", "measurement_goal", "destination_context"),
    required_any_fields=(("channels", "channel_context"),),
    recommended_outputs=(
        "UTM taxonomy",
        "Naming conventions",
        "Channel source medium mapping",
        "Campaign content term templates",
        "Destination URL checklist",
        "Event and pixel requirements",
        "Tracking QA checklist",
        "Reporting field map",
        "Attribution and privacy risk flags",
    ),
    output_sections=(
        "normalized_tracking_context",
        "utm_taxonomy_and_naming_conventions",
        "source_medium_channel_mapping",
        "campaign_content_term_templates",
        "destination_event_pixel_requirements",
        "tracking_qa_checklist",
        "reporting_handoff_and_risk_flags",
    ),
    handoff_targets=("Agent 21", "Agent 28"),
    forbidden_actions=("modify live url", "rewrite live url", "install tag", "install pixel", "create dashboard", "hide attribution", "launder attribution")
    + _COMMON_FORBIDDEN_ACTIONS,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_CLAIM_TERMS
    + ("hide attribution", "manipulate attribution", "prove tag firing", "verified in ga"),
    data_caveat_terms=("utm", "source", "medium", "event", "pixel", "conversion", "reporting"),
    quality_dimensions=(
        ("tracking_context_completeness", 15),
        ("utm_taxonomy_template_quality", 20),
        ("channel_source_medium_mapping", 15),
        ("event_pixel_reporting_requirements", 15),
        ("qa_checklist_and_missing_warning_quality", 15),
        ("attribution_privacy_no_live_edit_safety", 15),
        ("handoff_readiness", 5),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=35.0,
    billable_stage="generate_tracking_governance",
    metric_mode="tracking",
)

AGENT_26 = AgentProfile(
    agent_id="agent-26",
    number=26,
    slug="lead-routing-sla-design",
    title="Lead Routing & SLA Design Agent",
    package_label="LeadRoutingSLADesignPackage",
    purpose="Design routing, ownership, queue, fallback, escalation, and SLA rules from supplied operational context.",
    primary_object="lead routing and SLA design package",
    required_fields=("routing_objective", "sla_expectations"),
    required_any_fields=(("segment_context", "score_context", "qualification_context"), ("territory_context", "owner_context", "queue_context", "capacity_context")),
    recommended_outputs=(
        "Routing matrix",
        "Assignment rules",
        "Exception handling",
        "Territory and capacity considerations",
        "SLA definitions",
        "Escalation rules",
        "Queue and fallback logic",
        "Conflict warnings",
        "QA test scenarios",
    ),
    output_sections=(
        "normalized_routing_context",
        "routing_matrix",
        "assignment_rules_and_exception_handling",
        "territory_capacity_and_conflict_warnings",
        "sla_escalation_queue_fallback_logic",
        "protected_attribute_and_fairness_risks",
        "qa_test_scenarios_and_handoff",
    ),
    handoff_targets=("Agent 23", "Agent 28"),
    forbidden_actions=("update lead owner", "assign leads", "activate routing", "update territory", "send sales notification")
    + _COMMON_FORBIDDEN_ACTIONS,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_CLAIM_TERMS + ("routing is live", "owners updated"),
    data_caveat_terms=("territory", "capacity", "owner", "queue", "sla", "fallback", "score"),
    quality_dimensions=(
        ("routing_context_completeness", 15),
        ("routing_matrix_assignment_quality", 20),
        ("sla_escalation_fallback_quality", 15),
        ("territory_capacity_conflict_handling", 15),
        ("qa_scenario_coverage", 15),
        ("protected_attribute_fairness_no_activation_safety", 15),
        ("handoff_readiness", 5),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=45.0,
    billable_stage="generate_routing_sla_design",
    metric_mode="routing",
)

AGENT_27 = AgentProfile(
    agent_id="agent-27",
    number=27,
    slug="consent-compliance-review",
    title="Consent & Compliance Review Agent",
    package_label="ConsentComplianceReviewPackage",
    purpose="Review supplied campaign, audience, automation, tracking, consent, suppression, regional, and policy context for operational compliance risks.",
    primary_object="consent and compliance review package",
    required_fields=("compliance_context",),
    required_any_fields=(("region", "market_context"), ("consent_context", "suppression_context", "privacy_notes"), ("channels", "message_context")),
    recommended_outputs=(
        "Consent and suppression risk assessment",
        "Regional and data residency warnings",
        "Protected and sensitive targeting flags",
        "Privacy and data-use risk notes",
        "Brand and policy risk notes",
        "Required approvals and HITL notes",
        "Legal-review recommendation",
        "Mitigation checklist",
        "Not legal advice statement",
    ),
    output_sections=(
        "normalized_compliance_context",
        "consent_suppression_risk_assessment",
        "regional_data_residency_warnings",
        "protected_sensitive_targeting_flags",
        "privacy_brand_policy_risk_notes",
        "required_approvals_hitl_and_legal_review",
        "mitigation_checklist",
        "not_legal_advice_boundary",
    ),
    handoff_targets=("Agent 28",),
    forbidden_actions=("certify legal compliance", "certify policy compliance", "approve launch", "ignore regional", "ignore data residency")
    + _COMMON_FORBIDDEN_ACTIONS,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_CLAIM_TERMS + ("legally safe", "no legal review needed"),
    data_caveat_terms=("consent", "suppression", "privacy", "region", "data residency", "legal review"),
    quality_dimensions=(
        ("compliance_context_completeness", 15),
        ("consent_suppression_privacy_risk_quality", 20),
        ("regional_data_residency_risk_quality", 15),
        ("protected_sensitive_targeting_detection", 15),
        ("mitigation_hitl_legal_review_quality", 15),
        ("not_legal_advice_and_no_certification_safety", 15),
        ("handoff_readiness", 5),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=45.0,
    billable_stage="generate_compliance_review",
    metric_mode="compliance",
)

AGENT_28 = AgentProfile(
    agent_id="agent-28",
    number=28,
    slug="campaign-launch-readiness-qa",
    title="Campaign Launch Readiness QA Agent",
    package_label="CampaignLaunchReadinessQAPackage",
    purpose="Consolidate supplied campaign operational packages into a final human launch-readiness QA package.",
    primary_object="campaign launch readiness QA package",
    required_fields=("campaign_objective", "timeline"),
    required_any_fields=(("channels", "workflow_context"), ("tracking_context", "measurement_goal"), ("compliance_context", "consent_context")),
    recommended_outputs=(
        "Launch readiness score",
        "Human go no-go recommendation",
        "Blocking issues",
        "Warnings and caveats",
        "Asset checklist",
        "Tracking checklist",
        "Automation QA checklist",
        "Consent and suppression checklist",
        "Routing and SLA checklist",
        "Owner action list",
        "Final human approval requirements",
    ),
    output_sections=(
        "normalized_launch_context",
        "launch_readiness_score",
        "human_go_no_go_recommendation",
        "blocking_issues_and_warnings",
        "asset_tracking_automation_checklists",
        "consent_routing_approval_checklists",
        "owner_action_list",
        "reporting_handoff",
    ),
    handoff_targets=("Agent 21",),
    forbidden_actions=(
        "launch the campaign",
        "launch now",
        "schedule launch",
        "send now",
        "publish now",
        "activate campaign",
        "activate workflow",
        "approve launch",
        "mark unresolved blockers approved",
        "mark approved despite blockers",
    )
    + _COMMON_FORBIDDEN_ACTIONS,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_CLAIM_TERMS + ("no blockers", "qa certified", "launch approved"),
    data_caveat_terms=("blocker", "approval", "asset", "tracking", "workflow", "consent", "routing"),
    quality_dimensions=(
        ("core_launch_context_completeness", 15),
        ("blocker_preservation_and_warning_quality", 20),
        ("asset_tracking_checklist_coverage", 15),
        ("automation_consent_routing_qa_coverage", 20),
        ("owner_action_and_approval_clarity", 10),
        ("no_launch_approval_activation_safety", 15),
        ("reporting_handoff_readiness", 5),
    ),
    pass_threshold=85,
    approve_threshold=91,
    revise_min_threshold=70,
    cost_ceiling_inr=50.0,
    billable_stage="generate_launch_readiness_qa",
    metric_mode="launch",
)


_PROFILES = {
    profile.agent_id: profile
    for profile in (AGENT_22, AGENT_23, AGENT_24, AGENT_25, AGENT_26, AGENT_27, AGENT_28)
}


def get_profile(agent_id: str) -> AgentProfile:
    try:
        return _PROFILES[agent_id]
    except KeyError as exc:
        raise ValueError(f"unknown Marketing Operations agent profile: {agent_id}") from exc
