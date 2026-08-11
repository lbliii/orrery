"""Digest- and envelope-gated demand-side satisfaction (#68).

Ratings require a verified call receipt (``envelope_id``) or a documented
failed-call token (``call_attempt_id``). Name alone is insufficient.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from chirp.skill import Skill

VERDICTS: frozenset[str] = frozenset({"useful", "stale", "broken", "wrong-price"})
MAX_NOTE_LEN = 280


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


_default_store = InMemorySatisfactionStore()


def get_satisfaction_store() -> InMemorySatisfactionStore:
    """Return the process-wide in-memory satisfaction store."""
    return _default_store


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

    target = store or get_satisfaction_store()
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
    active_store = store or get_satisfaction_store()
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
