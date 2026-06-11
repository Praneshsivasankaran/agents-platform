variable "project_id" {
  type        = string
  description = "GCP project ID hosting Vertex AI, Speech-to-Text, and the transient STT bucket."
}

variable "region" {
  type        = string
  description = "Default region for regional resources (e.g. the transient STT bucket)."
  default     = "us-central1"
}

variable "service_account_id" {
  type        = string
  description = "Account ID (the part before @) for the platform service account."
  default     = "agents-platform-ci"

  validation {
    condition     = can(regex("^[a-z]([-a-z0-9]{4,28}[a-z0-9])$", var.service_account_id))
    error_message = "service_account_id must be 6-30 chars, lowercase letters/digits/hyphens, per GCP rules."
  }
}

variable "stt_bucket_name" {
  type        = string
  description = <<-EOT
    Globally-unique name for the DEDICATED transient Speech-to-Text bucket. Long-running
    recognition stages upload audio here briefly; the provider deletes each object immediately
    and the lifecycle rule below is a backstop. Do NOT reuse a content bucket.
  EOT
}

variable "stt_object_ttl_days" {
  type        = number
  description = "Lifecycle backstop: auto-delete any object older than this many days."
  default     = 1

  validation {
    condition     = var.stt_object_ttl_days >= 1 && var.stt_object_ttl_days <= 7
    error_message = "stt_object_ttl_days must be between 1 and 7 — this is a transient bucket."
  }
}

variable "github_repository" {
  type        = string
  description = "owner/repo allowed to assume the service account via WIF (e.g. 'pranesh/agents-platform')."

  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repository))
    error_message = "github_repository must be in 'owner/repo' form."
  }
}

variable "enabled_services" {
  type        = list(string)
  description = "GCP APIs to enable for the platform."
  default = [
    "aiplatform.googleapis.com", # Vertex AI (LLM)
    "speech.googleapis.com",     # Cloud Speech-to-Text
    "storage.googleapis.com",    # Cloud Storage (transient STT bucket)
    "secretmanager.googleapis.com",
    "iamcredentials.googleapis.com", # Workload Identity Federation token minting
  ]
}
