"""Storage abstraction for satellite products and derived artifacts.

Concepts: save(), save_stream(), get(), exists(), delete(), get_url().
Backends:
  * LocalStorageBackend  — local filesystem (development default)
  * S3StorageBackend     — any S3-compatible object store (production;
                           requires boto3, imported lazily)

Keys are forward-slash logical paths ("products/<scene>.zip"); no backend
leaks filesystem specifics into application code.
"""

from __future__ import annotations

import abc
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StoredFile:
    key: str
    size_bytes: int
    path: str | None   # local filesystem path when applicable
    url: str           # get_url() result


class StorageBackend(abc.ABC):
    @abc.abstractmethod
    def save(self, key: str, data: bytes) -> StoredFile: ...

    @abc.abstractmethod
    def save_stream(self, key: str, chunks, expected_size: int | None = None) -> StoredFile:
        """Persist an iterable of byte chunks without buffering in RAM."""

    @abc.abstractmethod
    def get(self, key: str) -> bytes: ...

    @abc.abstractmethod
    def exists(self, key: str) -> bool: ...

    @abc.abstractmethod
    def delete(self, key: str) -> None: ...

    @abc.abstractmethod
    def get_url(self, key: str) -> str: ...

    @abc.abstractmethod
    def get_path(self, key: str) -> Path:
        """Local filesystem path (LocalStorageBackend); S3 backends must
        download to a temporary cache first."""


def _validate_key(key: str) -> str:
    key = key.strip().replace("\\", "/").lstrip("/")
    if ".." in key.split("/"):
        raise ValueError(f"Illegal storage key: {key!r}")
    return key


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        return self.root / _validate_key(key)

    def save(self, key: str, data: bytes) -> StoredFile:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredFile(key, len(data), str(path), self.get_url(key))

    def save_stream(self, key: str, chunks, expected_size: int | None = None) -> StoredFile:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        size = 0
        try:
            with open(tmp, "wb") as fh:
                for chunk in chunks:
                    if chunk:
                        size += len(chunk)
                        if expected_size is not None and size > expected_size * 1.1:
                            raise IOError("Download exceeded advertised size")
                        fh.write(chunk)
            tmp.replace(path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        return StoredFile(key, size, str(path), self.get_url(key))

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)

    def get_url(self, key: str) -> str:
        return f"local://{_validate_key(key)}"

    def get_path(self, key: str) -> Path:
        return self._resolve(key)


class S3StorageBackend(StorageBackend):
    """S3-compatible object storage (AWS S3, MinIO, CloudFerro EOData...)."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        prefix: str = "sagar-watch",
        public_url_base: str | None = None,
    ) -> None:
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "STORAGE_BACKEND=s3 requires boto3: pip install boto3"
            ) from exc
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.public_url_base = public_url_base
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self._transfer = boto3.s3.transfer.TransferConfig(
            max_concurrency=4, use_threads=True
        )

    def _full(self, key: str) -> str:
        return f"{self.prefix}/{_validate_key(key)}"

    def save(self, key: str, data: bytes) -> StoredFile:
        full = self._full(key)
        self._client.put_object(Bucket=self.bucket, Key=full, Body=data)
        return StoredFile(key, len(data), None, self.get_url(key))

    def save_stream(self, key: str, chunks, expected_size: int | None = None) -> StoredFile:
        import io
        import tempfile

        buffer = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)
        size = 0
        try:
            for chunk in chunks:
                if chunk:
                    size += len(chunk)
                    buffer.write(chunk)
            buffer.seek(0)
            self._client.upload_fileobj(
                buffer, self.bucket, self._full(key), Config=self._transfer
            )
        finally:
            buffer.close()
        return StoredFile(key, size, None, self.get_url(key))

    def get(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self.bucket, Key=self._full(key))
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._full(key))
            return True
        except Exception:  # noqa: BLE001 — botocore ClientError family
            return False

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=self._full(key))

    def get_url(self, key: str) -> str:
        if self.public_url_base:
            return f"{self.public_url_base.rstrip('/')}/{self._full(key)}"
        return f"s3://{self.bucket}/{self._full(key)}"

    def get_path(self, key: str) -> Path:
        """Download to a local temp cache so rasterio can read it."""
        import tempfile

        cache_dir = Path(tempfile.gettempdir()) / "sagar-watch-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        local = cache_dir / key.replace("/", "_")
        if not local.exists():
            self._client.download_file(
                self.bucket, self._full(key), str(local), Config=self._transfer
            )
        return local


def create_storage(settings) -> StorageBackend:
    """Factory from application settings."""
    kind = settings.storage_backend.lower()
    if kind == "s3":
        return S3StorageBackend(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url or None,
            access_key=settings.s3_access_key or None,
            secret_key=settings.s3_secret_key or None,
        )
    return LocalStorageBackend(Path(settings.scene_storage_dir))
