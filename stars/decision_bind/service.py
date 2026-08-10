"""Seal planner decisions into offline-verifiable DecisionReceipt payloads."""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from .contract import MAX_DECISION_ID_LEN, MAX_STATEMENT_BYTES


def canonical_statement_bytes(statement: str) -> bytes:
    """UTF-8 bytes of ``statement`` after NFC normalization (ADR 0006)."""
    return unicodedata.normalize("NFC", statement).encode("utf-8")


def decision_digest(statement: str) -> str:
    """Lowercase hex sha256 of canonical statement bytes."""
    return hashlib.sha256(canonical_statement_bytes(statement)).hexdigest()


def bind(
    decision_id: str,
    statement: str,
    adr_url: str | None = None,
    issue_url: str | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Seal one bounded decision statement without hosting ADR or debate."""
    normalized_id = decision_id.strip() if isinstance(decision_id, str) else ""
    if not normalized_id or len(normalized_id) > MAX_DECISION_ID_LEN:
        return {"error": "decision_id_invalid", "decision_id": decision_id}

    if not isinstance(statement, str):
        return {"error": "statement_invalid"}

    normalized_statement = unicodedata.normalize("NFC", statement)
    statement_bytes = normalized_statement.encode("utf-8")
    if not normalized_statement:
        return {"error": "statement_empty"}
    if len(statement_bytes) > MAX_STATEMENT_BYTES:
        return {"error": "statement_too_large"}

    receipt: dict[str, object] = {
        "decision_id": normalized_id,
        "statement": normalized_statement,
        "decision_digest": decision_digest(normalized_statement),
        "decided_at": (clock or (lambda: datetime.now(UTC)))().isoformat(),
    }
    for field, url in (("adr_url", adr_url), ("issue_url", issue_url)):
        if url is None:
            continue
        if not isinstance(url, str) or not _valid_https_url(url):
            return {"error": "url_not_https", "field": field, "url": url}
        receipt[field] = url
    return receipt


def verify_receipt(payload: Mapping[str, Any]) -> dict[str, object]:
    """Verify DecisionReceipt digest rules offline (ADR 0006 rule 2)."""
    required = ("decision_id", "statement", "decision_digest", "decided_at")
    missing = [key for key in required if key not in payload]
    if missing:
        return {"verified": False, "error": "missing_fields", "missing": missing}

    statement = payload["statement"]
    digest = payload["decision_digest"]
    if not isinstance(statement, str):
        return {"verified": False, "error": "invalid_statement_type"}
    if not isinstance(digest, str):
        return {"verified": False, "error": "invalid_digest_type"}

    normalized = unicodedata.normalize("NFC", statement)
    if not normalized:
        return {"verified": False, "error": "statement_empty"}
    if len(normalized.encode("utf-8")) > MAX_STATEMENT_BYTES:
        return {"verified": False, "error": "statement_too_large"}

    expected = decision_digest(normalized)
    if digest != expected:
        return {
            "verified": False,
            "error": "digest_mismatch",
            "expected": expected,
            "received": digest,
        }

    for field in ("adr_url", "issue_url"):
        url = payload.get(field)
        if url is None:
            continue
        if not isinstance(url, str) or not _valid_https_url(url):
            return {"verified": False, "error": "url_not_https", "field": field}

    return {"verified": True}


def _valid_https_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.netloc)
