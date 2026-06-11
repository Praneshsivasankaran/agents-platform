"""Google Cloud Storage ObjectStorage implementation.

All google.cloud.storage imports are confined to this module.
"""
from __future__ import annotations

from core.interfaces.object_storage import ObjectStorage


class GCSObjectStorage(ObjectStorage):
    """Google Cloud Storage backend.

    Bucket and prefix are configured via cfg. No credentials in code —
    uses Application Default Credentials (ADC) or workload identity.

    Issue 5: Bucket name can come from either:
      - cfg.object_storage.bucket  (direct name)
      - cfg.object_storage.bucket_secret_key  (env var / SecretStore key resolved at init)
    """

    name = "gcs"

    def __init__(self, cfg: dict, secret_store=None) -> None:
        storage_cfg = cfg.get("object_storage", {})
        self._prefix: str = storage_cfg.get("prefix", "")

        # Resolve bucket name: direct config OR via SecretStore/env
        bucket_direct = storage_cfg.get("bucket", "")
        bucket_secret_key = storage_cfg.get("bucket_secret_key", "")

        if bucket_secret_key:
            # Issue 4 Fix C: Require SecretStore — no os.environ fallback.
            if secret_store is None:
                raise ValueError(
                    f"GCSObjectStorage: bucket_secret_key={bucket_secret_key!r} requires a SecretStore. "
                    f"Factory should have injected one automatically."
                )
            val = secret_store.get(bucket_secret_key)
            if not val:
                raise ValueError(
                    f"GCSObjectStorage: SecretStore.get({bucket_secret_key!r}) returned empty"
                )
            self._bucket_name = val
        elif bucket_direct:
            self._bucket_name = bucket_direct
        else:
            raise ValueError(
                "GCSObjectStorage: cfg.object_storage must have either "
                "'bucket' (direct name) or 'bucket_secret_key' (env var name)"
            )

        # Lazy import — defer google-cloud-storage import to first use
        project_direct = storage_cfg.get("project", "")
        project_secret_key = storage_cfg.get("project_secret_key", "")
        if project_secret_key:
            if secret_store is None:
                raise ValueError(
                    f"GCSObjectStorage: project_secret_key={project_secret_key!r} requires a SecretStore"
                )
            project_value = secret_store.get(project_secret_key)
            if not project_value:
                raise ValueError(
                    f"GCSObjectStorage: SecretStore.get({project_secret_key!r}) returned empty"
                )
            self._project = project_value
        elif project_direct:
            self._project = project_direct
        else:
            self._project = None

        self._client = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import storage as gcs  # type: ignore[import-untyped]
            self._client = gcs.Client(project=self._project)
        return self._client

    def _validate_key(self, key: str) -> None:
        """Recommended improvement: validate GCS object keys before use."""
        if not key or not key.strip():
            raise ValueError("GCSObjectStorage: object key must be non-empty")
        if key.startswith("/"):
            raise ValueError(f"GCSObjectStorage: key must be relative, not absolute: {key!r}")
        if ".." in key.split("/"):
            raise ValueError(f"GCSObjectStorage: key must not contain '..' components: {key!r}")

    def _full_key(self, key: str) -> str:
        if self._prefix:
            return f"{self._prefix.rstrip('/')}/{key}"
        return key

    def put(self, key: str, data: bytes) -> str:
        self._validate_key(key)
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._full_key(key))
        blob.upload_from_string(data)
        return key

    def get(self, key: str) -> bytes:
        self._validate_key(key)
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._full_key(key))
        return blob.download_as_bytes()

    def delete(self, key: str) -> None:
        self._validate_key(key)
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._full_key(key))
        blob.delete()

    def uri_for(self, key: str) -> str:
        """Return the provider URI for a validated key.

        This provider-specific helper is used inside other GCP provider modules
        (for example long-running Cloud Speech); agent logic still sees only the
        ObjectStorage interface.
        """
        self._validate_key(key)
        return f"gs://{self._bucket_name}/{self._full_key(key)}"
