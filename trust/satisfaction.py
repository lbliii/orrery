"""Digest- and envelope-gated demand-side satisfaction (#68).

Ratings require a verified call receipt (``envelope_id``) or a documented
failed-call token (``call_attempt_id``). Name alone is insufficient.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from chirp.skill import Skill

VERDICTS: frozenset[str] = frozenset({"useful", "stale", "broken", "wrong-price"})
MAX_NOTE_LEN = 280
DEFAULT_WINDOW = "7d"
DEFAULT_WINDOW_DAYS = 7


@dataclass(frozen=True, slots=True)
class SatisfactionRecord:
    """One demand-side rating keyed by digest + receipt authority."""

    star_name: str
    content_digest: str
    verdict: str
    created_at: str
    envelope_id: str | None = None
    call_attempt_id: str | None = None
    note: str | None = None
    caller_namespace: str | None = None

    def receipt_key(self) -> tuple[str, str]:
        """Primary store key fragment: digest + authority id."""
        authority = self.envelope_id or self.call_attempt_id or ""
        return (self.content_digest, authority)

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "star_name": self.star_name,
            "content_digest": self.content_digest,
            "verdict": self.verdict,
            "created_at": self.created_at,
        }
        if self.envelope_id is not None:
            payload["envelope_id"] = self.envelope_id
        if self.call_attempt_id is not None:
            payload["call_attempt_id"] = self.call_attempt_id
        if self.note is not None:
            payload["note"] = self.note
        if self.caller_namespace is not None:
            payload["caller_namespace"] = self.caller_namespace
        return payload


@dataclass(frozen=True, slots=True)
class SatisfactionAggregate:
    """Counts per verdict for one ``(star_name, content_digest)`` slice."""

    star_name: str
    content_digest: str
    counts: dict[str, int] = field(default_factory=dict)
    total: int = 0
    window: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "star_name": self.star_name,
            "content_digest": self.content_digest,
            "counts": dict(self.counts),
            "total": self.total,
            "window": self.window,
        }


class SatisfactionStore(Protocol):
    def put(self, record: SatisfactionRecord) -> SatisfactionRecord: ...

    def get_for_receipt(
        self,
        *,
        content_digest: str,
        envelope_id: str | None,
        call_attempt_id: str | None,
    ) -> SatisfactionRecord | None: ...

    def aggregate(
        self,
        *,
        star_name: str,
        content_digest: str,
        since: datetime | None = None,
    ) -> SatisfactionAggregate: ...

    def records_for(self, star_name: str) -> tuple[SatisfactionRecord, ...]: ...


class SatisfactionStoreUnavailable(RuntimeError):
    """Raised when a durable store is required but DATABASE_URL is unset."""

    code = "store_unavailable"


class InMemorySatisfactionStore:
    """Process-local stub store for #68 / #69."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], SatisfactionRecord] = {}

    def put(self, record: SatisfactionRecord) -> SatisfactionRecord:
        self._records[record.receipt_key()] = record
        return record

    def get_for_receipt(
        self,
        *,
        content_digest: str,
        envelope_id: str | None,
        call_attempt_id: str | None,
    ) -> SatisfactionRecord | None:
        authority = envelope_id or call_attempt_id
        if not authority:
            return None
        return self._records.get((content_digest, authority))

    def aggregate(
        self,
        *,
        star_name: str,
        content_digest: str,
        since: datetime | None = None,
    ) -> SatisfactionAggregate:
        counts: Counter[str] = Counter()
        for record in self._records.values():
            if record.star_name != star_name:
                continue
            if record.content_digest != content_digest:
                continue
            if since is not None:
                created = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
                if created < since:
                    continue
            counts[record.verdict] += 1
        ordered = {verdict: counts[verdict] for verdict in sorted(counts)}
        return SatisfactionAggregate(
            star_name=star_name,
            content_digest=content_digest,
            counts=ordered,
            total=sum(counts.values()),
        )

    def records_for(self, star_name: str) -> tuple[SatisfactionRecord, ...]:
        """All stored ratings for one Skill DNS name (any digest)."""
        return tuple(
            record for record in self._records.values() if record.star_name == star_name
        )


_default_store: SatisfactionStore | None = None


def get_satisfaction_store() -> SatisfactionStore:
    """Return the process-wide store (Postgres when DATABASE_URL is set).

    Tests inject ``InMemorySatisfactionStore`` via ``_default_store``. Without a
    URL, gaze / pills use an in-memory stub so CI pages do not 500. Writes
    still fail closed via ``submit_rate`` when no URL and no injected store.
    """
    global _default_store
    if _default_store is not None:
        return _default_store
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        _default_store = InMemorySatisfactionStore()
        return _default_store
    from trust.satisfaction_postgres import PostgresSatisfactionStore

    store = PostgresSatisfactionStore(database_url=database_url)
    store.initialize()
    _default_store = store
    return store


@dataclass(frozen=True, slots=True)
class SatisfactionPillView:
    """Compact demand-side pill for gaze / resolve / star surfaces (#69)."""

    total: int = 0
    useful_pct: int | None = None
    window: str | None = None
    pill_text: str | None = None
    pill_class: str = "pill-priv"

    @property
    def quiet(self) -> bool:
        """True when there is no digest-matched aggregate to show."""
        return self.total <= 0 or not self.pill_text

    def as_dict(self) -> dict[str, object]:
        if self.quiet:
            return {"quiet": True}
        return {
            "quiet": False,
            "pill_text": self.pill_text,
            "pill_class": self.pill_class,
            "useful_pct": self.useful_pct,
            "total": self.total,
            "window": self.window,
        }


def _since_for_window(window: str | None) -> datetime | None:
    if window == DEFAULT_WINDOW:
        return datetime.now(UTC) - timedelta(days=DEFAULT_WINDOW_DAYS)
    return None


def aggregate_for_live_digest(
    *,
    star_name: str,
    content_digest: str,
    store: SatisfactionStore | None = None,
    window: str = DEFAULT_WINDOW,
) -> SatisfactionAggregate:
    """Aggregate ratings for the live resolve digest only (mismatch ⇒ empty)."""
    target = store or get_satisfaction_store()
    digest = _normalize_digest(content_digest)
    agg = target.aggregate(
        star_name=star_name.strip(),
        content_digest=digest,
        since=_since_for_window(window),
    )
    if agg.total <= 0:
        return agg
    return SatisfactionAggregate(
        star_name=agg.star_name,
        content_digest=agg.content_digest,
        counts=agg.counts,
        total=agg.total,
        window=window,
    )


def satisfaction_pill_for(
    *,
    star_name: str,
    content_digest: str,
    store: SatisfactionStore | None = None,
    window: str = DEFAULT_WINDOW,
) -> SatisfactionPillView:
    """Build a compact pill or a quiet empty view — never fake scores."""
    agg = aggregate_for_live_digest(
        star_name=star_name,
        content_digest=content_digest,
        store=store,
        window=window,
    )
    if agg.total <= 0:
        return SatisfactionPillView(total=0, window=window)
    useful = agg.counts.get("useful", 0)
    pct = round(useful * 100 / agg.total)
    return SatisfactionPillView(
        total=agg.total,
        useful_pct=pct,
        window=window,
        pill_text=f"{pct}% useful · {agg.total}/{window}",
    )


def _normalize_digest(value: str) -> str:
    digest = value.strip()
    if digest.startswith("sha256:"):
        return digest
    return f"sha256:{digest}"


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def submit_rate(
    *,
    star_name: str,
    content_digest: str,
    verdict: str,
    envelope_id: str = "",
    call_attempt_id: str = "",
    note: str = "",
    caller_namespace: str = "",
    receipt: dict[str, Any] | None = None,
    store: SatisfactionStore | None = None,
    verify_receipt: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, object]:
    """Validate and persist one envelope-gated rating. No wallet side effects."""
    name = star_name.strip()
    digest = _normalize_digest(content_digest)
    env_id = envelope_id.strip()
    attempt_id = call_attempt_id.strip()
    verdict_value = verdict.strip()

    if not name:
        return {"status": "rejected", "error": "missing_star_name"}
    if not digest or digest == "sha256:":
        return {"status": "rejected", "error": "missing_content_digest"}
    if verdict_value not in VERDICTS:
        return {"status": "rejected", "error": "invalid_verdict", "allowed": sorted(VERDICTS)}
    if env_id and attempt_id:
        return {"status": "rejected", "error": "conflicting_receipt_authority"}
    if not env_id and not attempt_id:
        return {"status": "rejected", "error": "missing_receipt_authority"}

    note_value = note.strip() or None
    if note_value is not None and len(note_value) > MAX_NOTE_LEN:
        return {"status": "rejected", "error": "note_too_long", "max_len": MAX_NOTE_LEN}

    if env_id:
        if receipt is None:
            return {"status": "rejected", "error": "missing_receipt"}
        if verify_receipt is None:
            return {"status": "rejected", "error": "receipt_verifier_unconfigured"}
        wire = {k: v for k, v in receipt.items() if k not in ("payment_id", "price_per_call")}
        if not verify_receipt(wire):
            return {"status": "rejected", "error": "invalid_receipt"}
        receipt_nonce = str(receipt.get("nonce") or "")
        if receipt_nonce != env_id:
            return {"status": "rejected", "error": "envelope_id_mismatch"}

    if store is not None:
        target = store
    elif not os.environ.get("DATABASE_URL", "").strip():
        return {"status": "rejected", "error": "store_unavailable"}
    else:
        target = get_satisfaction_store()
    record = SatisfactionRecord(
        star_name=name,
        content_digest=digest,
        envelope_id=env_id or None,
        call_attempt_id=attempt_id or None,
        verdict=verdict_value,
        note=note_value,
        caller_namespace=caller_namespace.strip() or None,
        created_at=_utc_now_iso(),
    )
    stored = target.put(record)
    return {"status": "ok", "record": stored.as_dict()}


def build_satisfaction_skill(
    *,
    private_key: Any | None = None,
    verify_receipt: Callable[[dict[str, Any]], bool] | None = None,
    store: SatisfactionStore | None = None,
) -> Skill:
    """MCP skill exposing post-call ``rate`` (aggregate host mount)."""
    import os

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    def _load_key(env_name: str) -> Ed25519PrivateKey:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
        return Ed25519PrivateKey.generate()

    private = private_key or _load_key("ORRERY_SATISFACTION_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "satisfaction",
        version="1.0.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_SATISFACTION_KEY_ID", "satisfaction-1"),
        public_key=public,
    )
    active_store = store
    verifier = verify_receipt

    @skill.tool(
        "rate",
        description=(
            "Post-call satisfaction verdict (useful | stale | broken | wrong-price). "
            "Requires envelope_id from a verified call receipt or call_attempt_id "
            "for a failed call. Name alone is insufficient."
        ),
    )
    def rate(
        star_name: str,
        content_digest: str,
        verdict: str,
        envelope_id: str = "",
        call_attempt_id: str = "",
        note: str = "",
        caller_namespace: str = "",
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        return submit_rate(
            star_name=star_name,
            content_digest=content_digest,
            verdict=verdict,
            envelope_id=envelope_id,
            call_attempt_id=call_attempt_id,
            note=note,
            caller_namespace=caller_namespace,
            receipt=receipt,
            store=active_store,
            verify_receipt=verifier,
        )

    @skill.tool(
        "star_rate",
        description="Alias for ``rate`` — envelope-gated star satisfaction verdict.",
    )
    def star_rate(
        star_name: str,
        content_digest: str,
        verdict: str,
        envelope_id: str = "",
        call_attempt_id: str = "",
        note: str = "",
        caller_namespace: str = "",
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        return submit_rate(
            star_name=star_name,
            content_digest=content_digest,
            verdict=verdict,
            envelope_id=envelope_id,
            call_attempt_id=call_attempt_id,
            note=note,
            caller_namespace=caller_namespace,
            receipt=receipt,
            store=active_store,
            verify_receipt=verifier,
        )

    return skill
