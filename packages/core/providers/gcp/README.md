# GCP Provider Implementations

LiteLLM-backed LLM provider and Google Cloud Storage backend for the agents platform.

## LiteLLMProvider

Routes LLM calls to Vertex AI via LiteLLM. Tier to model resolution from config.

**Required config keys:**
- `llm.tier_models.cheap` — Vertex model for cheap tier (e.g. `vertex_ai/gemini-2.5-flash`)
- `llm.tier_models.strong` — Vertex model for strong tier
- `llm.vertex_location` — Vertex AI region (e.g. `us-central1`)
- `cost.fx_rates.USD` — INR/USD conversion rate (LiteLLM always reports cost in USD)
- `cost.input_cost_per_token_inr` — per-tier fallback input pricing in INR/token
- `cost.output_cost_per_token_inr` — per-tier fallback output pricing in INR/token

**Credentials:** Use Application Default Credentials (ADC) or set `GOOGLE_APPLICATION_CREDENTIALS`.

## Pricing (Google Vertex AI standard tier, June 2026)

Source: https://cloud.google.com/vertex-ai/generative-ai/docs/pricing

| Tier   | Model                | Input (USD/1M) | Output (USD/1M) | Input (INR/token) | Output (INR/token) |
|--------|----------------------|----------------|-----------------|-------------------|--------------------|
| cheap  | gemini-2.5-flash     | $0.30          | $2.50           | 0.0000249         | 0.0002075          |
| strong | gemini-2.5-pro       | $1.25          | $10.00          | 0.0001037         | 0.0008300          |

Formula: `$(price/1M) × ₹83 / 1,000,000 = ₹ per token` (at USD/INR = 83.0)

Rates are pessimistic (never lower than official).

Model availability is time-sensitive. Verify configured Vertex model IDs against Google's model
lifecycle page before every release and live-smoke run.
https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions

## GCSObjectStorage

Thin wrapper around `google.cloud.storage`. Bucket and prefix from config.

**Required config keys:**
- `object_storage.bucket` (direct name) OR `object_storage.bucket_secret_key` (env var via SecretStore)
- `object_storage.prefix` — key prefix (e.g. `blog-agent/v1/`)

## Running the live smoke test

```bash
export VERTEX_AI_PROJECT=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
PYTHONPATH=packages:agents/agent-01-blog-writer \
  python -m pytest agents/agent-01-blog-writer/tests/smoke -q -v
```
