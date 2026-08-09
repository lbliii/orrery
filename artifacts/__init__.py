"""Durable artifact metadata and object-storage ports.

The package deliberately contains metadata and storage interfaces only.  Web
processes must retrieve artifacts through these ports rather than retain bytes
in a process-local dictionary.
"""

from .capabilities import (
    ArtifactCapabilityService,
    ArtifactCapabilitySettings,
    ObjectCapability,
    UploadIntent,
)
from .cleanup import ArtifactCleanupService, CleanupResult
from .domain import (
    ArtifactPolicy,
    ArtifactRecord,
    ArtifactState,
    PostgresArtifactRepository,
    artifact_storage_key,
)
from .storage import ArtifactStorage, InMemoryObjectStorage, S3ObjectStorage

__all__ = [
    "ArtifactCapabilityService",
    "ArtifactCapabilitySettings",
    "ArtifactCleanupService",
    "ArtifactPolicy",
    "ArtifactRecord",
    "ArtifactState",
    "ArtifactStorage",
    "CleanupResult",
    "InMemoryObjectStorage",
    "ObjectCapability",
    "PostgresArtifactRepository",
    "S3ObjectStorage",
    "UploadIntent",
    "artifact_storage_key",
]
