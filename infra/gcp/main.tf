# agents-platform — GCP infrastructure (Cycle 4 scaffold).
#
# Provisions exactly what the live gate needs, least-privilege, keyless:
#   - required APIs
#   - one platform service account
#   - a Workload Identity Federation pool + GitHub OIDC provider (NO service-account JSON keys)
#   - a dedicated TRANSIENT Speech-to-Text bucket with a lifecycle delete backstop
#   - project-level IAM (aiplatform.user, speech.client, secretmanager accessor)
#   - bucket-scoped IAM (objectAdmin) on the transient bucket only
#
# SECURITY: there is deliberately NO `google_service_account_key` resource anywhere. CI auth is
# via WIF OIDC only. Long-lived exported keys are the thing we are avoiding.

# ---------------------------------------------------------------------------
# 1. Enable required APIs
# ---------------------------------------------------------------------------
resource "google_project_service" "enabled" {
  for_each = toset(var.enabled_services)

  project = var.project_id
  service = each.value

  # Keep APIs enabled even if this resource is destroyed — destroying API enablement can
  # disrupt other workloads in a shared project.
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# 2. Platform service account (the identity CI/WIF impersonates)
# ---------------------------------------------------------------------------
resource "google_service_account" "platform" {
  project      = var.project_id
  account_id   = var.service_account_id
  display_name = "agents-platform CI/runtime (Vertex + Speech + transient GCS)"
  description  = "Least-privilege identity for Agent 01+ live calls. Assumed via WIF; no exported keys."
}

# ---------------------------------------------------------------------------
# 3. Workload Identity Federation — GitHub Actions OIDC (keyless CI)
# ---------------------------------------------------------------------------
resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions"
  description               = "OIDC federation for agents-platform CI (merge-queue live smoke)."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Hard-restrict token exchange to THIS repository. Without this condition any GitHub repo
  # could mint tokens for the pool.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Allow the GitHub repo (via the pool) to impersonate the service account.
resource "google_service_account_iam_member" "wif_impersonation" {
  service_account_id = google_service_account.platform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# ---------------------------------------------------------------------------
# 4. Transient Speech-to-Text bucket (uniform access, lifecycle delete backstop)
# ---------------------------------------------------------------------------
resource "google_storage_bucket" "stt_transient" {
  project                     = var.project_id
  name                        = var.stt_bucket_name
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # Backstop: auto-delete any live object older than the TTL. The provider already deletes
  # each transient object immediately after recognition; this guards against a missed delete.
  lifecycle_rule {
    condition {
      age        = var.stt_object_ttl_days
      with_state = "LIVE"
    }
    action {
      type = "Delete"
    }
  }

  # Clean up dangling/aborted resumable uploads after one day.
  lifecycle_rule {
    condition {
      age                        = 1
      days_since_noncurrent_time = 1
    }
    action {
      type = "Delete"
    }
  }
}

# ---------------------------------------------------------------------------
# 5. IAM — least privilege
# ---------------------------------------------------------------------------
# Project-level: Vertex AI user + Speech client + Secret Manager accessor.
resource "google_project_iam_member" "roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/speech.client",
    "roles/secretmanager.secretAccessor",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.platform.email}"
}

# Bucket-scoped: objectAdmin on the transient bucket ONLY (put/get/delete the STT objects).
# Deliberately NOT project-wide storage admin.
resource "google_storage_bucket_iam_member" "stt_object_admin" {
  bucket = google_storage_bucket.stt_transient.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.platform.email}"
}
