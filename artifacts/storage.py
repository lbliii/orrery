"""S3-compatible object storage boundary for durable artifact bytes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ArtifactStorage(Protocol):
    def put(self, *, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, *, key: str) -> bytes | None: ...

    def delete(self, *, key: str) -> None: ...


@dataclass(frozen=True)
class ObjectMetadata:
    """The object attributes required to finalize an artifact upload."""

    byte_length: int
    content_type: str
    sha256: str | None


class CapabilityObjectStorage(ArtifactStorage, Protocol):
    """Storage which can issue an object-scoped capability without exposing keys."""

    def issue_put_url(
        self, *, key: str, expires_in: int, content_type: str, sha256: str
    ) -> str: ...

    def issue_get_url(self, *, key: str, expires_in: int) -> str: ...

    def head(self, *, key: str) -> ObjectMetadata | None: ...


class S3ObjectStorage:
    """Small adapter over an S3-compatible client (AWS S3, R2, Railway, MinIO)."""

    def __init__(self, client: Any, *, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, *, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, *, key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            if self._is_not_found(exc):
                return None
            raise
        return response["Body"].read()

    def delete(self, *, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def issue_put_url(
        self, *, key: str, expires_in: int, content_type: str, sha256: str
    ) -> str:
        """Issue a PUT URL restricted to one key, type, and checksum metadata.

        Workers receive this URL rather than bucket credentials.  The required
        ``x-amz-meta-sha256`` header is checked again by ``head`` at completion.
        """
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
                "Metadata": {"sha256": sha256},
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )

    def issue_get_url(self, *, key: str, expires_in: int) -> str:
        """Issue a short-lived GET URL restricted to one object."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
            HttpMethod="GET",
        )

    def head(self, *, key: str) -> ObjectMetadata | None:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            if self._is_not_found(exc):
                return None
            raise
        metadata = response.get("Metadata", {})
        return ObjectMetadata(
            byte_length=int(response["ContentLength"]),
            content_type=str(response.get("ContentType", "")),
            sha256=str(metadata["sha256"]) if metadata.get("sha256") else None,
        )

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        code = str(response.get("Error", {}).get("Code", ""))
        return code in {"404", "NoSuchKey", "NotFound"}


class InMemoryObjectStorage:
    """Test double with S3 semantics; production code must supply a real adapter."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put(self, *, key: str, data: bytes, content_type: str) -> None:
        self._objects[key] = (data, content_type)

    def get(self, *, key: str) -> bytes | None:
        item = self._objects.get(key)
        return item[0] if item is not None else None

    def delete(self, *, key: str) -> None:
        self._objects.pop(key, None)
