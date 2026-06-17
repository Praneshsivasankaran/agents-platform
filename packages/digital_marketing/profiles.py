"""Agent-specific Digital Marketing profiles.

The shared workflow stays small and provider-neutral. Profiles carry the
agent-specific scope, required inputs, output sections, risk boundaries, and
quality rubric for Agents 15-21.
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
    "ad platform api",
    "automatically launch",
    "change budget",
    "crawl",
    "edit ads",
    "email everyone",
    "fetch live",
    "launch campaign",
    "pause campaign",
    "publish",
    "query analytics",
    "query dashboard",
    "read search console",
    "schedule posts",
    "scrape",
    "send email",
    "send report",
    "send sms",
    "spend budget",
    "sync to crm",
    "update cms",
    "update crm",
    "upload audience",
)

_UNSUPPORTED_METRIC_TERMS = (
    "invent cpc",
    "invent search volume",
    "make up cpc",
    "make up ctr",
    "make up roas",
    "make up search volume",
    "pretend we have data",
    "guarantee ranking",
    "guarantee rank",
    "guaranteed conversions",
    "guaranteed roas",
    "guaranteed lift",
)

_DECEPTIVE_TERMS = (
    "dark pattern",
    "fake countdown",
    "fake scarcity",
    "mislead",
    "trick users",
)

AGENT_15 = AgentProfile(
    agent_id="agent-15",
    number=15,
    slug="keyword-research",
    title="Keyword Research Agent",
    package_label="KeywordResearchPackage",
    purpose="Build an evidence-aware keyword strategy from supplied context and keyword data.",
    primary_object="keyword strategy",
    required_fields=("product_or_service", "campaign_goal", "target_audience"),
    required_any_fields=(("keywords", "keyword_table", "source_notes"),),
    recommended_outputs=(
        "Keyword clusters",
        "Intent classification",
        "Funnel-stage mapping",
        "Priority keywords",
        "Negative keyword recommendations",
        "Page and ad-group mapping",
        "Missing metric warnings",
    ),
    output_sections=(
        "normalized_request_summary",
        "keyword_clusters",
        "intent_and_funnel_map",
        "priority_and_negative_keywords",
        "page_ad_group_content_mapping",
        "missing_metric_warnings",
    ),
    handoff_targets=("Agent 16", "Agent 17", "Agent 18", "Agent 19", "Agent 21"),
    forbidden_actions=("rank check", "serp crawl", "search console", "seo tool", "keyword api", "guarantee rankings")
    + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_METRIC_TERMS
    + ("estimate live cpc", "estimate live search volume", "rank number one"),
    data_caveat_terms=("search volume", "cpc", "difficulty", "rank", "ranking"),
    quality_dimensions=(
        ("input_normalization_metric_honesty", 15),
        ("keyword_cluster_quality", 20),
        ("intent_funnel_classification", 15),
        ("priority_rationale_evidence_use", 15),
        ("negative_keyword_exclusion_usefulness", 10),
        ("page_ad_group_content_mapping", 10),
        ("risk_policy_handling", 10),
        ("downstream_handoff_readiness", 5),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=35.0,
    billable_stage="generate_keyword_strategy",
    metric_mode="keyword",
)

AGENT_16 = AgentProfile(
    agent_id="agent-16",
    number=16,
    slug="ad-copy-creation",
    title="Ad Copy Creation Agent",
    package_label="AdCopyCreationPackage",
    purpose="Draft safe ad copy variants and message briefs from supplied campaign context.",
    primary_object="ad copy package",
    required_fields=("campaign_goal", "target_audience", "offer", "brand_voice"),
    required_any_fields=(("platforms", "channels"),),
    recommended_outputs=(
        "Search ad variants",
        "Social ad variants",
        "Headline and description sets",
        "CTA options",
        "Message angles",
        "A/B test ideas",
        "Claim evidence map",
        "Compliance warnings",
    ),
    output_sections=(
        "normalized_campaign_summary",
        "message_angles",
        "platform_copy_variants",
        "claim_evidence_map",
        "ab_test_ideas",
        "compliance_policy_warnings",
    ),
    handoff_targets=("Agent 18", "Agent 19", "Agent 21"),
    forbidden_actions=("bypass policy", "launch ads", "upload ads", "approve ads", "upload audience")
    + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_METRIC_TERMS
    + ("cure", "diagnose", "guaranteed returns", "legally proven", "risk-free investment"),
    data_caveat_terms=("ctr", "cpc", "cvr", "roas", "conversion rate"),
    quality_dimensions=(
        ("audience_offer_alignment", 15),
        ("message_angle_distinctness", 15),
        ("platform_format_fit", 15),
        ("claim_evidence_compliance_safety", 20),
        ("copy_clarity_cta_strength", 15),
        ("ab_test_usefulness", 10),
        ("risk_review_readiness", 10),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=35.0,
    billable_stage="generate_ad_copy_package",
    metric_mode="copy",
)

AGENT_17 = AgentProfile(
    agent_id="agent-17",
    number=17,
    slug="landing-page-optimization",
    title="Landing Page Optimization Agent",
    package_label="LandingPageOptimizationPackage",
    purpose="Create a review-ready landing page optimization brief from supplied page context.",
    primary_object="landing page optimization brief",
    required_fields=("campaign_goal", "target_audience", "offer"),
    required_any_fields=(("page_copy", "page_notes", "page_sections"),),
    recommended_outputs=(
        "Message-match review",
        "Hero recommendations",
        "CTA recommendations",
        "Form friction review",
        "Trust proof gaps",
        "Content hierarchy improvements",
        "Accessibility and usability warnings",
        "A/B test ideas",
        "Implementation brief",
    ),
    output_sections=(
        "normalized_page_summary",
        "message_match_review",
        "hero_cta_and_form_findings",
        "proof_hierarchy_and_usability_gaps",
        "ab_test_ideas",
        "implementation_brief",
    ),
    handoff_targets=("Agent 20", "Agent 21"),
    forbidden_actions=("crawl url", "fetch page", "publish page", "update cms", "read heatmap", "read analytics")
    + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_METRIC_TERMS + _DECEPTIVE_TERMS + ("claim conversion lift",),
    data_caveat_terms=("conversion lift", "bounce rate", "heatmap", "analytics", "form completion"),
    quality_dimensions=(
        ("message_match_offer_clarity", 20),
        ("hero_cta_actionability", 15),
        ("form_friction_conversion_path_review", 15),
        ("trust_proof_objection_handling", 15),
        ("content_hierarchy_usability", 10),
        ("seo_ad_relevance_notes", 10),
        ("test_ideas_implementation_brief", 10),
        ("risk_privacy_handling", 5),
    ),
    pass_threshold=82,
    approve_threshold=88,
    revise_min_threshold=65,
    cost_ceiling_inr=40.0,
    billable_stage="generate_landing_page_brief",
    metric_mode="page",
)

AGENT_18 = AgentProfile(
    agent_id="agent-18",
    number=18,
    slug="paid-campaign-optimization",
    title="Paid Campaign Optimization Agent",
    package_label="PaidCampaignOptimizationPackage",
    purpose="Recommend paid campaign optimizations from supplied performance summaries.",
    primary_object="paid campaign optimization package",
    required_fields=("campaign_goal",),
    required_any_fields=(("platforms", "channels"), ("campaign_export", "metric_summary", "metrics", "source_notes")),
    recommended_outputs=(
        "Optimization findings",
        "Campaign structure issues",
        "Advisory budget recommendations",
        "Keyword creative audience placement actions",
        "Wasted-spend and pacing flags",
        "Experiment plan",
        "Missing denominator warnings",
    ),
    output_sections=(
        "normalized_performance_summary",
        "metric_tied_findings",
        "optimization_recommendations",
        "advisory_budget_and_pacing",
        "experiment_plan",
        "missing_data_denominator_warnings",
    ),
    handoff_targets=("Agent 19", "Agent 20", "Agent 21"),
    forbidden_actions=("change bid", "change budgets", "edit ads", "launch campaign", "pause campaign", "upload audience")
    + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_METRIC_TERMS + ("optimize without data", "guarantee roas"),
    data_caveat_terms=("ctr", "cpc", "cvr", "cpa", "roas", "spend", "conversions", "impressions", "clicks"),
    quality_dimensions=(
        ("supplied_data_grounding", 20),
        ("metric_denominator_correctness", 15),
        ("campaign_structure_diagnosis", 15),
        ("keyword_creative_audience_placement_actionability", 15),
        ("advisory_budget_pacing_guidance", 10),
        ("experiment_plan_quality", 10),
        ("risk_policy_no_activation_handling", 10),
        ("downstream_handoff_readiness", 5),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=45.0,
    billable_stage="generate_paid_optimization_package",
    metric_mode="paid",
)

AGENT_19 = AgentProfile(
    agent_id="agent-19",
    number=19,
    slug="multi-channel-campaign-planning",
    title="Multi-Channel Campaign Planning Agent",
    package_label="MultiChannelCampaignPlanningPackage",
    purpose="Turn a chosen campaign direction into a coordinated channel execution plan.",
    primary_object="multi-channel campaign plan",
    required_fields=("campaign_goal", "target_audience", "offer", "timeline"),
    required_any_fields=(("channels", "platforms"),),
    recommended_outputs=(
        "Channel strategy",
        "Channel mix",
        "Campaign calendar",
        "Message sequencing",
        "Asset requirements",
        "Channel-specific briefs",
        "Dependency map",
        "Measurement plan",
    ),
    output_sections=(
        "normalized_campaign_brief",
        "channel_strategy_and_mix",
        "calendar_and_sequence",
        "asset_dependency_owner_map",
        "channel_briefs",
        "measurement_plan",
    ),
    handoff_targets=("Agent 21",),
    forbidden_actions=("schedule", "send", "publish", "write workflow", "bypass consent", "bypass suppression")
    + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_METRIC_TERMS + _DECEPTIVE_TERMS,
    data_caveat_terms=("budget", "timeline", "owner", "asset", "kpi"),
    quality_dimensions=(
        ("strategy_audience_offer_alignment", 20),
        ("channel_mix_sequencing_quality", 15),
        ("calendar_feasibility", 15),
        ("asset_dependency_completeness", 15),
        ("channel_brief_actionability", 15),
        ("measurement_plan_quality", 10),
        ("consent_suppression_activation_safety", 10),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=50.0,
    billable_stage="generate_campaign_plan",
    metric_mode="planning",
)

AGENT_20 = AgentProfile(
    agent_id="agent-20",
    number=20,
    slug="conversion-rate-optimization",
    title="Conversion Rate Optimization Agent",
    package_label="ConversionRateOptimizationPackage",
    purpose="Create a disciplined CRO diagnosis, hypothesis backlog, and experiment plan.",
    primary_object="CRO experiment plan",
    required_fields=("conversion_goal", "target_audience"),
    required_any_fields=(("page_copy", "page_notes", "page_sections", "funnel_stages"), ("metric_summary", "metrics", "source_notes")),
    recommended_outputs=(
        "CRO diagnosis",
        "Hypothesis backlog",
        "Prioritized experiment plan",
        "Prioritization scores",
        "Form CTA content friction recommendations",
        "Measurement plan",
        "Sample-size and data caveats",
    ),
    output_sections=(
        "normalized_cro_context",
        "friction_diagnosis",
        "hypothesis_backlog",
        "experiment_prioritization",
        "measurement_plan",
        "sample_size_data_caveats",
    ),
    handoff_targets=("Agent 21",),
    forbidden_actions=("launch experiment", "change website", "update website", "personalize automatically", "ignore consent")
    + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_METRIC_TERMS
    + _DECEPTIVE_TERMS
    + ("prove lift", "guarantee lift", "statistically significant without data"),
    data_caveat_terms=("conversion lift", "baseline", "sample size", "denominator", "traffic"),
    quality_dimensions=(
        ("diagnosis_specificity_evidence_use", 20),
        ("hypothesis_quality", 20),
        ("prioritization_transparency", 15),
        ("measurement_plan_quality", 15),
        ("data_sample_caveat_handling", 10),
        ("form_cta_content_friction_actionability", 10),
        ("privacy_consent_manipulation_safety", 10),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=45.0,
    billable_stage="generate_cro_plan",
    metric_mode="cro",
)

AGENT_21 = AgentProfile(
    agent_id="agent-21",
    number=21,
    slug="performance-reporting",
    title="Performance Reporting Agent",
    package_label="PerformanceReportingPackage",
    purpose="Create truthful stakeholder-ready performance reports from supplied metrics.",
    primary_object="performance reporting package",
    required_fields=("campaign_goal", "reporting_period"),
    required_any_fields=(("metric_summary", "metrics", "channel_summaries", "source_notes"),),
    recommended_outputs=(
        "Executive summary",
        "KPI scorecard",
        "Channel performance table",
        "Deterministic calculations",
        "Campaign highlights and risks",
        "Budget spend summary",
        "Recommendations and next steps",
        "Stakeholder variants",
        "Data-quality caveats",
    ),
    output_sections=(
        "normalized_reporting_context",
        "executive_summary",
        "kpi_scorecard",
        "channel_performance_table",
        "deterministic_calculations",
        "caveats_recommendations_next_steps",
        "stakeholder_variants",
    ),
    handoff_targets=("Future optimization cycle",),
    forbidden_actions=("hide bad results", "misrepresent", "query live analytics", "send reports", "publish dashboard")
    + _ACTIVATION_FORBIDDEN,
    protected_terms=_PROTECTED_TERMS,
    unsupported_claim_terms=_UNSUPPORTED_METRIC_TERMS
    + ("hide negative", "make performance look better", "fake improvement", "overstate attribution"),
    data_caveat_terms=("ctr", "cpc", "cvr", "cpa", "roas", "revenue", "spend", "pipeline", "delta"),
    quality_dimensions=(
        ("metric_kpi_correctness", 20),
        ("data_quality_attribution_caveat_handling", 15),
        ("executive_summary_clarity", 15),
        ("channel_performance_table_usefulness", 15),
        ("recommendation_next_step_actionability", 15),
        ("stakeholder_variant_fit", 10),
        ("truthfulness_misrepresentation_safety", 10),
    ),
    pass_threshold=84,
    approve_threshold=90,
    revise_min_threshold=68,
    cost_ceiling_inr=45.0,
    billable_stage="generate_performance_report",
    metric_mode="reporting",
)


_PROFILES = {
    profile.agent_id: profile
    for profile in (AGENT_15, AGENT_16, AGENT_17, AGENT_18, AGENT_19, AGENT_20, AGENT_21)
}


def get_profile(agent_id: str) -> AgentProfile:
    try:
        return _PROFILES[agent_id]
    except KeyError as exc:
        raise ValueError(f"unknown Digital Marketing agent profile: {agent_id}") from exc
