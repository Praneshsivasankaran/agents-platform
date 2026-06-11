# infra/gcp — GCP infrastructure (Terraform)

Provisions the platform's GCP footprint, least-privilege and **keyless** (Workload Identity
Federation; no exported service-account JSON keys). Wired first; AWS/Azure stay stubbed.

## What this creates
- **APIs**: Vertex AI, Speech-to-Text, Cloud Storage, Secret Manager, IAM Credentials.
- **Service account** `agents-platform-ci` — the identity CI impersonates via WIF.
- **Workload Identity Federation** pool + GitHub OIDC provider, restricted to one repo
  (`attribute_condition` on `assertion.repository`). This is what `google-github-actions/auth`
  uses in `.github/workflows/ci.yaml`.
- **Transient STT bucket** with uniform access, public-access prevention, and a lifecycle
  **delete** backstop (default 1 day). Long-running Speech recognition uploads audio here
  briefly; the provider deletes each object immediately (see
  `packages/core/providers/gcp/transcription.py`), and the lifecycle rule is the backstop.
- **IAM**: project-level `aiplatform.user`, `speech.client`, `secretmanager.secretAccessor`;
  bucket-scoped `storage.objectAdmin` on the transient bucket only.

## Files
| File | Purpose |
|------|---------|
| `versions.tf` | Terraform + provider version pins; (commented) GCS remote-state backend. |
| `variables.tf` | Inputs (project, region, bucket, repo, TTL) with validation. |
| `main.tf` | All resources. **No `google_service_account_key`** anywhere. |
| `outputs.tf` | The four values to set as GitHub secrets (SA email, WIF provider, bucket, project). |
| `terraform.tfvars.example` | Copy → `terraform.tfvars` and fill in. |

## Usage
```bash
cd infra/gcp
cp terraform.tfvars.example terraform.tfvars   # then edit
terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply        # human action; requires owner/editor on the project
```
Then set the four `terraform output` values as GitHub repository/environment secrets:
`GCP_SERVICE_ACCOUNT`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCS_BLOG_BUCKET`, `VERTEX_AI_PROJECT`.

## Status
Cycle 4 **scaffold** — written and self-consistent, **not yet `terraform apply`-ed**. Run
`fmt`/`validate`/`plan` where Terraform is installed before applying. The live smoke gate
currently runs against a manually-provisioned project; this codifies that footprint so it is
reproducible and reviewable.
