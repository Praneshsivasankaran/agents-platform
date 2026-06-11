output "service_account_email" {
  description = "Set this as the GCP_SERVICE_ACCOUNT GitHub secret (live-smoke job)."
  value       = google_service_account.platform.email
}

output "workload_identity_provider" {
  description = <<-EOT
    Set this as the GCP_WORKLOAD_IDENTITY_PROVIDER GitHub secret. Full resource name consumed by
    google-github-actions/auth in .github/workflows/ci.yaml.
  EOT
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "stt_bucket_name" {
  description = "Set this as the GCS_BLOG_BUCKET GitHub secret and in config/gcp.yaml."
  value       = google_storage_bucket.stt_transient.name
}

output "vertex_ai_project" {
  description = "Set this as the VERTEX_AI_PROJECT GitHub secret."
  value       = var.project_id
}
