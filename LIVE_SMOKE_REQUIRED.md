# Live GCP provider smoke gate - required before merge

Increments 5 and 6 require credentialed live Vertex AI and Cloud Speech-to-Text
verification. Offline tests cannot satisfy this merge gate.

## Required GCP setup

1. Use a billing-enabled GCP project.
2. Enable the APIs:

   ```bash
   gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID
   gcloud services enable speech.googleapis.com --project=YOUR_PROJECT_ID
   gcloud services enable storage.googleapis.com --project=YOUR_PROJECT_ID
   ```

3. Create a dedicated transient-audio GCS bucket. Configure a short lifecycle
   deletion rule as a backstop in case a process is interrupted before cleanup.
4. Create a least-privilege service account. Grant only:
   - `roles/aiplatform.user`
   - `roles/speech.client`
   - bucket-scoped `roles/storage.objectAdmin` on the dedicated transient-audio
     bucket
5. Configure GitHub Actions Workload Identity Federation. Do not create a
   long-lived service-account key.
6. Create the protected GitHub environment `vertex-production` with a required
   human reviewer.
7. Add environment secrets:
   - `GCP_WORKLOAD_IDENTITY_PROVIDER`
   - `GCP_SERVICE_ACCOUNT`
   - `VERTEX_AI_PROJECT`
   - `GCS_BLOG_BUCKET`
8. Enable the merge queue for `main`.
9. Require the status check `Live GCP provider smoke gate (required)`.

## Required live tests

`agents/agent-01-blog-writer/tests/smoke/test_smoke_gcp.py` must pass:

1. Exact configured Vertex model/project/location forwarding.
2. Real Vertex text response with positive finite usage/cost.
3. Real Vertex structured response with positive finite usage/cost.
4. GCP overlay selects the priced real transcription provider.
5. Real Cloud Speech call returns successfully and records positive provider-native cost.
6. Real long-running Cloud Speech call uses transient GCS storage above the
   synchronous threshold and completes cleanup.

The transcription smoke sends one second of generated silence. A successful Speech
response is expected to contain no transcript, so the provider raises the content-free
`response_empty` billable category. Permission, API, or network failures produce
`provider_call_failed` and fail the smoke.

The long-form smoke uses 56 seconds of generated silence, just above the
55-second synchronous threshold. It must finish with `response_empty`; GCS
upload, Speech long-running recognition, or deletion failures fail the gate.

## CI behavior

The `live-smoke` job runs only for `merge_group` or direct pushes to `main`, after
offline CI passes. It has no skip guards. Missing credentials, missing APIs, incorrect
IAM, unavailable models, or provider-call failures fail the job.

Before each release, verify the configured Vertex model IDs and the configured
Cloud Speech pricing estimate against the provider's current lifecycle/pricing pages.
