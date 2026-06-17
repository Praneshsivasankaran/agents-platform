# Agent 16 - Ad Copy Creation Agent

Agent 16 drafts safe ad copy variants and creative-message briefs for Digital Marketing. It is advisory only: it does not upload ads, launch campaigns, bypass platform policies, upload audiences, approve ads, or spend budget.

## Provider Modes

Config files live in `config/`:

- `base.yaml` - mock/offline provider for tests
- `gcp.yaml` - live GCP/Vertex overlay through LiteLLM and `LLMProvider`
- `bedrock.yaml` - AWS stub-compatible overlay
- `azure.yaml` - Azure stub-compatible overlay

Model names and cloud selection live in config only. Agent code never imports cloud SDKs or direct model SDKs.

## Run Locally

```powershell
$env:PYTHONPATH = "packages;agents\agent-16-ad-copy-creation"
.\.agent02-ui-venv\Scripts\python.exe -m pytest agents\agent-16-ad-copy-creation\tests -q
```

Service usage:

```python
from agent.service import run

package = run({
    "campaign_goal": "Generate demo requests",
    "target_audience": "RevOps leaders",
    "offer": "Lead handoff maturity assessment",
    "brand_voice": "Clear and practical",
    "platforms": ["Google Search", "LinkedIn"],
})
```

## V1 Boundaries

No ad platform writes, publishing, audience uploads, spend, or auto-approval are allowed. Claims must be tied to supplied proof or flagged for human review.
