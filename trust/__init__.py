"""Trust surfaces — publish-oracle status for resolve/star UI (#34)."""

from .oracle import (
    OracleView,
    configure_oracle,
    oracle_for,
    record_skill_scores,
    record_skill_scores_from_registry,
    smoke_slice_for_skill,
)

__all__ = [
    "OracleView",
    "configure_oracle",
    "oracle_for",
    "record_skill_scores",
    "record_skill_scores_from_registry",
    "smoke_slice_for_skill",
]
