# Agent 27 - Consent & Compliance Review Agent

Agent 27 triages consent, suppression, privacy, regional, data-residency, protected-targeting, policy, and legal-review risks. It is advisory only and returns a schema-valid Marketing Operations review package for human use inside the future MarketingIQ Studio surface. No standalone UI is included in this batch.

## Provider Modes

Config files live in config/:

- ase.yaml - mock/offline provider for tests
- gcp.yaml - live GCP/Vertex overlay through LiteLLM and LLMProvider
- edrock.yaml - AWS Bedrock stub-compatible overlay
- zure.yaml - Azure AI/Azure OpenAI stub-compatible overlay

Model names, object storage, secrets, telemetry, and cloud selection live in config only. Agent code never imports cloud SDKs, direct model SDKs, litellm, or external platform SDKs.

## Run Locally

`powershell
$env:PYTHONPATH = "packages;agents\agent-27-consent-compliance-review"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-27-consent-compliance-review\tests -q
`

Service usage:

`python
from agent.service import run

package = run({
    # Required context shape: compliance_context, region/market context, consent/suppression/privacy context, channels/message context
})
`

## V1 Boundaries

Allowed inputs are direct user-supplied notes, summaries, and upstream handoffs only. Forbidden in v1: legal advice, compliance certification, live consent reads, suppression edits, audience uploads, launch approval, or external system writes. Optional artifact persistence must go through ObjectStorage; secrets through SecretStore; model calls through LLMProvider; telemetry through Telemetry.

## Testing

The test suite includes schema, scoring, workflow, no-cloud-SDK, eval, and GCP overlay smoke tests. Live GCP smoke is gated by RUN_MARKETING_OPERATIONS_GCP_SMOKE=1 and VERTEX_AI_PROJECT.