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
    SatisfactionPillView,
    SatisfactionRecord,
    SatisfactionStore,
    aggregate_for_live_digest,
    get_satisfaction_store,
    satisfaction_pill_for,
    submit_rate,
)

__all__ = [
    "InMemorySatisfactionStore",
    "OracleView",
    "SatisfactionAggregate",
    "SatisfactionPillView",
    "SatisfactionRecord",
    "SatisfactionStore",
    "aggregate_for_live_digest",
    "configure_oracle",
    "get_satisfaction_store",
    "oracle_for",
    "record_skill_scores",
    "record_skill_scores_from_registry",
    "satisfaction_pill_for",
    "smoke_slice_for_skill",
    "submit_rate",
]
