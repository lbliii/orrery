"""Trust surfaces — publish-oracle status for resolve/star UI (#34)."""

from .oracle import (
    OracleView,
    configure_oracle,
    oracle_for,
    record_skill_scores,
    record_skill_scores_from_registry,
    smoke_slice_for_skill,
)
from .satisfaction import (
    InMemorySatisfactionStore,
    SatisfactionAggregate,
    SatisfactionRecord,
    SatisfactionStore,
    get_satisfaction_store,
    submit_rate,
)

__all__ = [
    "InMemorySatisfactionStore",
    "OracleView",
    "SatisfactionAggregate",
    "SatisfactionRecord",
    "SatisfactionStore",
    "configure_oracle",
    "get_satisfaction_store",
    "oracle_for",
    "record_skill_scores",
    "record_skill_scores_from_registry",
    "smoke_slice_for_skill",
    "submit_rate",
]
