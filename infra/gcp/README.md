# infra/gcp — FIRST target

Terraform for the GCP deployment (wired first): a least-privilege service account,
Secret Manager entries (provider/STT keys for `SecretStore`), and a Cloud Storage bucket
for `ObjectStorage` (short/no retention on raw media — DESIGN §10).

Bodies land during Debug/Harden; v1 proves the agent on GCP/Vertex.
