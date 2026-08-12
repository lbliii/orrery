"""Framework-neutral building blocks for Star packages."""

from .attribution import PAYLOAD_VIA, with_via
from .corpus import (
    StarCorpusError,
    corpus_ok_by_star,
    load_publish_corpus,
    require_nonempty_corpus,
    validate_public_star_corpora,
)
from .definition import StarDefinition, StarManifest, StarManifestError
from .execution import ManagedCPUExecutionPolicy, ManagedCPUExecutionPolicyError, ManagedCPUWorkload
from .registry import StarRegistry

__all__ = [
    "PAYLOAD_VIA",
    "ManagedCPUExecutionPolicy",
    "ManagedCPUExecutionPolicyError",
    "ManagedCPUWorkload",
    "StarCorpusError",
    "StarDefinition",
    "StarManifest",
    "StarManifestError",
    "StarRegistry",
    "corpus_ok_by_star",
    "load_publish_corpus",
    "require_nonempty_corpus",
    "validate_public_star_corpora",
    "with_via",
]
