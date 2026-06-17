"""Agent-specific Demand Generation profiles.

Profiles keep the shared implementation honest: every agent uses the same
platform mechanics, but validation focus, output objects, scoring dimensions,
and forbidden-action boundaries remain agent-specific.
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
    recommended_outputs: tuple[str, ...]
    handoff_targets: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    protected_terms: tuple[str, ...]
    leaky_terms: tuple[str, ...]
    quality_dimensions: tuple[QualityDimension, ...]
    pass_threshold: int
    approve_threshold: int
    revise_min_threshold: int
    cost_ceiling_inr: float
    billable_stage: str
    llm_tier: str = "strong"
    metric_mode: str = "standard"


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
)

_ACTIVATION_FORBIDDEN = (
    "activate",
    "automatically launch",
    "buy contacts",
    "buy lead list",
    "change budget",
    "create contacts",
    "enrich contacts",
    "enrich leads",
    "pause campaign",
    "publish",
    "run experiment",
    "scrape",
    "send email",
    "send sms",
    "send messages",
    "spend budget",
    "sync to crm",
    "update crm",
    "update marketing automation",
    "upload audience",
)


AGENT_08 = AgentProfile(
    agent_id="agent-08",
    number=8,
    slug="icp-identification",
    title="ICP Identification Agent",
    package_label="ICPIdentificationPackage",
    purpose="Identify evidence-backed Ideal Customer Profiles for demand generation planning.",
    primary_object="ICP profile",
    required_fields=("business_context", "product_or_service", "source_notes"),
    recommended_outputs=(
        "Ranked ICP profiles",
        "Fit signals",
        "Disqualifiers",
        "Buying committee map",
        "Evidence map",
        "Assumption register",
    ),
    handoff_targets=("Agent 09", "Agent 10", "Agent 11", "Agent 12", "Agent 13"),
    forbidden_actions=("create account list", "enrich accounts", "scrape accounts", "update crm") + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    leaky_terms=(),
    quality_dimensions=(
        ("evidence_strength_traceability", 20),
        ("icp_specificity_without_overfitting", 15),
        ("actionable_fit_criteria", 15),
        ("disqualifiers_guardrails", 10),
        ("buying_committee_clarity", 10),
        ("pain_value_trigger_usefulness", 10),
        ("compliance_safety", 10),
        ("downstream_handoff_readiness", 5),
        ("executive_usability", 5),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=35.0,
    billable_stage="generate_icp_profiles",
)

AGENT_09 = AgentProfile(
    agent_id="agent-09",
    number=9,
    slug="audience-segmentation",
    title="Audience Segmentation Agent",
    package_label="AudienceSegmentationPackage",
    purpose="Turn ICP and campaign context into operational audience segments.",
    primary_object="audience segment",
    required_fields=("icp_summary", "campaign_goal", "audience_fields"),
    recommended_outputs=(
        "Segment definitions",
        "Inclusion rules",
        "Exclusion rules",
        "Overlap checks",
        "Suppression rules",
        "Channel and message fit",
    ),
    handoff_targets=("Agent 10", "Agent 11", "Agent 12", "Agent 13"),
    forbidden_actions=("estimate audience size without data", "upload audiences") + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    leaky_terms=(),
    quality_dimensions=(
        ("segment_distinctness_non_overlap", 20),
        ("inclusion_exclusion_rule_clarity", 15),
        ("campaign_objective_alignment", 15),
        ("persona_pain_message_relevance", 15),
        ("data_availability_feasibility", 10),
        ("suppression_compliance_handling", 10),
        ("downstream_handoff_readiness", 10),
        ("operational_usability", 5),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=30.0,
    billable_stage="generate_segments",
)

AGENT_10 = AgentProfile(
    agent_id="agent-10",
    number=10,
    slug="lead-generation",
    title="Lead Generation Agent",
    package_label="LeadGenerationPackage",
    purpose="Create a lead generation campaign blueprint, not individual lead records.",
    primary_object="lead generation campaign blueprint",
    required_fields=("icp_summary", "segment_summary", "campaign_goal", "offer"),
    recommended_outputs=(
        "Campaign motion",
        "Offer recommendation",
        "Capture path",
        "Landing page brief",
        "Form brief",
        "Qualification rules",
        "KPI plan",
    ),
    handoff_targets=("Agent 11", "Agent 12", "Agent 13", "Agent 14"),
    forbidden_actions=("generate contact list", "buy lead list", "scrape contacts", "enrich contacts") + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    leaky_terms=(),
    quality_dimensions=(
        ("icp_segment_alignment", 20),
        ("offer_channel_fit", 15),
        ("funnel_capture_path_completeness", 15),
        ("landing_page_form_clarity", 10),
        ("qualification_scoring_handoff", 10),
        ("experiment_kpi_design", 10),
        ("operational_feasibility", 10),
        ("consent_compliance_handling", 5),
        ("executive_clarity", 5),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=40.0,
    billable_stage="generate_lead_gen_blueprint",
)

AGENT_11 = AgentProfile(
    agent_id="agent-11",
    number=11,
    slug="lead-scoring",
    title="Lead Scoring Agent",
    package_label="LeadScoringPackage",
    purpose="Design rule-based, explainable lead scoring logic.",
    primary_object="lead scoring model",
    required_fields=("icp_summary", "segment_summary", "signals"),
    recommended_outputs=(
        "Signal taxonomy",
        "Weights",
        "Score bands",
        "Thresholds",
        "Sample explanations",
        "Routing handoff",
        "Data quality warnings",
    ),
    handoff_targets=("Agent 13", "Agent 14"),
    forbidden_actions=("train black-box model", "update crm score", "update map score", "route leads automatically") + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    leaky_terms=("closed won", "converted", "opportunity created", "revenue won", "sql accepted", "won revenue"),
    quality_dimensions=(
        ("signal_relevance_icp_alignment", 20),
        ("explainability_weights_thresholds", 15),
        ("data_quality_completeness", 15),
        ("fit_engagement_intent_balance", 15),
        ("bias_protected_leakage_safety", 10),
        ("routing_nurture_actionability", 10),
        ("calibration_guidance", 10),
        ("operational_clarity", 5),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=50.0,
    billable_stage="generate_scoring_model",
)

AGENT_12 = AgentProfile(
    agent_id="agent-12",
    number=12,
    slug="campaign-recommendation",
    title="Campaign Recommendation Agent",
    package_label="CampaignRecommendationPackage",
    purpose="Rank campaign plays and explain the recommended campaign path.",
    primary_object="campaign recommendation",
    required_fields=("segment_summary", "campaign_goal", "budget", "constraints"),
    recommended_outputs=(
        "Ranked campaign options",
        "Primary recommendation",
        "Alternatives",
        "Budget guidance",
        "KPI and experiment plan",
        "Dependencies",
        "Risk register",
    ),
    handoff_targets=("Agent 10", "Agent 13", "Agent 14"),
    forbidden_actions=("launch ads", "send emails", "spend budget", "upload audiences") + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    leaky_terms=(),
    quality_dimensions=(
        ("goal_audience_fit", 20),
        ("channel_recommendation_rationale", 15),
        ("budget_timeline_practicality", 15),
        ("offer_asset_alignment", 10),
        ("kpi_experiment_design", 10),
        ("dependency_operational_readiness", 10),
        ("risk_compliance_handling", 10),
        ("ranking_executive_usability", 10),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=45.0,
    billable_stage="generate_campaign_recommendations",
)

AGENT_13 = AgentProfile(
    agent_id="agent-13",
    number=13,
    slug="lead-nurturing",
    title="Lead Nurturing Agent",
    package_label="LeadNurturingPackage",
    purpose="Design compliant lead nurture journeys without sending messages.",
    primary_object="nurture journey",
    required_fields=("segment_summary", "score_bands", "campaign_goal", "content_inventory"),
    recommended_outputs=(
        "Journey map",
        "Branches",
        "Touchpoints",
        "Cadence",
        "Triggers and exits",
        "Suppression rules",
        "Content gaps",
        "Sales handoff",
    ),
    handoff_targets=("Agent 14",),
    forbidden_actions=("send email", "send sms", "write map workflow", "update crm", "activate retargeting") + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    leaky_terms=(),
    quality_dimensions=(
        ("journey_logic_branch_clarity", 20),
        ("segment_score_band_alignment", 15),
        ("content_relevance_gap_handling", 15),
        ("cadence_timing_quality", 10),
        ("personalization_usefulness", 10),
        ("consent_suppression_compliance", 10),
        ("sales_handoff_actionability", 10),
        ("kpi_experiment_clarity", 5),
        ("operational_clarity", 5),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=40.0,
    billable_stage="generate_nurture_journey",
)

AGENT_14 = AgentProfile(
    agent_id="agent-14",
    number=14,
    slug="conversion-analysis",
    title="Conversion Analysis Agent",
    package_label="ConversionAnalysisPackage",
    purpose="Analyze supplied conversion data with deterministic metric math first.",
    primary_object="conversion analysis",
    required_fields=("campaign_goal", "funnel_stages"),
    recommended_outputs=(
        "Funnel diagnostics",
        "Conversion rates",
        "Drop-off analysis",
        "Bottleneck ranking",
        "Root-cause hypotheses",
        "Optimization recommendations",
        "Experiment backlog",
    ),
    handoff_targets=("Agent 10", "Agent 11", "Agent 12", "Agent 13"),
    forbidden_actions=("change budget", "pause campaign", "launch experiment", "modify live systems") + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    leaky_terms=(),
    quality_dimensions=(
        ("metric_math_correctness", 20),
        ("data_quality_caveat_handling", 15),
        ("bottleneck_specificity", 20),
        ("evidence_backed_hypotheses", 15),
        ("recommendation_prioritization", 15),
        ("experiment_measurement_clarity", 10),
        ("executive_clarity", 5),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=50.0,
    billable_stage="generate_conversion_insights",
    metric_mode="conversion",
)


_PROFILES = {
    profile.agent_id: profile
    for profile in (AGENT_08, AGENT_09, AGENT_10, AGENT_11, AGENT_12, AGENT_13, AGENT_14)
}


def get_profile(agent_id: str) -> AgentProfile:
    try:
        return _PROFILES[agent_id]
    except KeyError as exc:
        raise ValueError(f"unknown Demand Generation agent profile: {agent_id}") from exc

