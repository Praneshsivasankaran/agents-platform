"""Offline interface tests for GCSObjectStorage.

google.cloud.storage is mocked — no credentials or network needed.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest

_CFG = {
    "object_storage": {
        "provider": "gcp",
        "bucket": "test-bucket",
        "prefix": "blog-agent/v1/",
    }
}

_CFG_NO_BUCKET = {
    "object_storage": {"provider": "gcp", "prefix": "blog/"}
}


class TestGCSObjectStorage:
    def test_missing_bucket_raises(self):
        from core.providers.gcp.storage import GCSObjectStorage
        with pytest.raises(ValueError, match="bucket"):
            GCSObjectStorage(_CFG_NO_BUCKET)

    def _make_storage(self):
        from core.providers.gcp.storage import GCSObjectStorage
        return GCSObjectStorage(_CFG)

    def test_put_calls_upload(self):
        s = self._make_storage()
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        s._client = mock_client

        s.put("test/key.json", b'{"hello": "world"}')

        mock_client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("blog-agent/v1/test/key.json")
        mock_blob.upload_from_string.assert_called_once_with(b'{"hello": "world"}')

    def test_put_returns_key(self):
        s = self._make_storage()
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        s._client = MagicMock()
        s._client.bucket.return_value = mock_bucket

        result = s.put("some/key.json", b"data")
        assert result == "some/key.json"

    def test_get_calls_download(self):
        s = self._make_storage()
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"content"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        s._client = mock_client

        result = s.get("some/key")
        assert result == b"content"
        mock_bucket.blob.assert_called_once_with("blog-agent/v1/some/key")

    def test_delete_calls_blob_delete(self):
        s = self._make_storage()
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        s._client = mock_client

        s.delete("some/key")
        mock_blob.delete.assert_called_once()

    def test_prefix_applied(self):
        s = self._make_storage()
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        s._client = mock_client

        s.put("myfile.txt", b"data")
        full_key = mock_bucket.blob.call_args[0][0]
        assert full_key == "blog-agent/v1/myfile.txt"

    def test_no_prefix_uses_key_directly(self):
        from core.providers.gcp.storage import GCSObjectStorage
        cfg = {"object_storage": {"provider": "gcp", "bucket": "b", "prefix": ""}}
        s = GCSObjectStorage(cfg)
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        s._client = MagicMock()
        s._client.bucket.return_value = mock_bucket
        s.put("direct.txt", b"x")
        mock_bucket.blob.assert_called_once_with("direct.txt")

    def test_prefix_trailing_slash_normalized(self):
        """Prefix with trailing slash should not produce double slashes."""
        from core.providers.gcp.storage import GCSObjectStorage
        cfg = {"object_storage": {"provider": "gcp", "bucket": "b", "prefix": "myprefix/"}}
        s = GCSObjectStorage(cfg)
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        s._client = MagicMock()
        s._client.bucket.return_value = mock_bucket
        s.put("file.txt", b"x")
        full_key = mock_bucket.blob.call_args[0][0]
        assert "//" not in full_key
        assert full_key == "myprefix/file.txt"

    def test_lazy_client_init(self):
        """Client is None until first use."""
        from core.providers.gcp.storage import GCSObjectStorage
        s = GCSObjectStorage(_CFG)
        assert s._client is None

    def test_secret_bucket_wins_over_inherited_direct_bucket(self):
        from core.providers.gcp.storage import GCSObjectStorage

        secrets = MagicMock()
        secrets.get.side_effect = lambda key: {
            "GCS_BLOG_BUCKET": "real-cloud-bucket",
            "VERTEX_AI_PROJECT": "real-project",
        }[key]
        cfg = {
            "object_storage": {
                "provider": "gcp",
                "bucket": "mock-bucket",
                "bucket_secret_key": "GCS_BLOG_BUCKET",
                "project_secret_key": "VERTEX_AI_PROJECT",
            }
        }

        storage = GCSObjectStorage(cfg, secret_store=secrets)

        assert storage._bucket_name == "real-cloud-bucket"
        assert storage._project == "real-project"

    def test_lazy_client_receives_resolved_project(self):
        from core.providers.gcp.storage import GCSObjectStorage

        secrets = MagicMock()
        secrets.get.return_value = "configured-project"
        cfg = {
            "object_storage": {
                "provider": "gcp",
                "bucket": "test-bucket",
                "project_secret_key": "VERTEX_AI_PROJECT",
            }
        }
        storage = GCSObjectStorage(cfg, secret_store=secrets)
        fake_client = MagicMock()

        with patch("google.cloud.storage.Client", return_value=fake_client) as client_cls:
            assert storage._get_client() is fake_client

        client_cls.assert_called_once_with(project="configured-project")
