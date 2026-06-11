terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }

  # Remote state is recommended for shared/CI use. Configure a GCS backend after the
  # state bucket exists (chicken-and-egg: create the bucket on local state first, then
  # migrate). Left commented so `terraform init` works out of the box for a dry run.
  #
  # backend "gcs" {
  #   bucket = "REPLACE_ME-tfstate"
  #   prefix = "agents-platform/gcp"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
