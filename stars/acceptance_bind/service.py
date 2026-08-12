"""Seal sprint acceptance criteria into offline-verifiable AcceptanceReceipt payloads."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from .contract import (
    MAX_ACCEPTANCE_ID_LEN,
    MAX_CRITERIA,
    MAX_CRITERION_ID_LEN,
    MAX_STATEMENT_BYTES,
    MAX_VERIFY_EXPECT_LEN,
    MAX_VERIFY_REF_LEN,
    VERIFY_KINDS,
)

_CRITERION_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def canonical_acceptance_bytes(acceptance_id: str, criteria: Sequence[Mapping[str, Any]]) -> bytes:
    """UTF-8 canonical acceptance bytes per ADR 0009 section 4."""
    normalized_id = unicodedata.normalize("NFC", acceptance_id)
    sorted_criteria = sorted(criteria, key=lambda item: str(item["id"]))
    canonical_criteria: list[dict[str, object]] = []
    for item in sorted_criteria:
        verify_raw = item["verify"]
        verify: dict[str, str] = {
            "kind": str(verify_raw["kind"]),
            "ref": unicodedata.normalize("NFC", str(verify_raw["ref"])),
        }
        if "expect" in verify_raw and verify_raw["expect"] is not None:
            verify["expect"] = unicodedata.normalize("NFC", str(verify_raw["expect"]))
        canonical_criteria.append(
            {
                "id": unicodedata.normalize("NFC", str(item["id"])),
                "statement": unicodedata.normalize("NFC", str(item["statement"])),
                "verify": verify,
            }
        )
    payload = {
        "acceptance_id": normalized_id,
        "criteria": canonical_criteria,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def acceptance_digest(acceptance_id: str, criteria: Sequence[Mapping[str, Any]]) -> str:
    """Lowercase hex sha256 of canonical acceptance bytes."""
    return hashlib.sha256(canonical_acceptance_bytes(acceptance_id, criteria)).hexdigest()


def bind(
    acceptance_id: str,
    criteria: object,
    adr_url: str | None = None,
    issue_url: str | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Seal bounded acceptance criteria without executing verify refs."""
    normalized_id = acceptance_id.strip() if isinstance(acceptance_id, str) else ""
    if not normalized_id or len(normalized_id) > MAX_ACCEPTANCE_ID_LEN:
        return {"error": "acceptance_id_invalid", "acceptance_id": acceptance_id}

    normalized_id = unicodedata.normalize("NFC", normalized_id)

    if not isinstance(criteria, list):
        return {"error": "criteria_invalid"}
    if not criteria:
        return {"error": "criteria_empty"}
    if len(criteria) > MAX_CRITERIA:
        return {"error": "criteria_too_many", "max_criteria": MAX_CRITERIA}

    normalized_criteria: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(criteria):
        parsed = _parse_criterion(raw, index)
        if "error" in parsed:
            return parsed
        criterion_id = str(parsed["id"])
        if criterion_id in seen_ids:
            return {"error": "duplicate_criterion_id", "id": criterion_id}
        seen_ids.add(criterion_id)
        normalized_criteria.append(parsed)

    receipt: dict[str, object] = {
        "acceptance_id": normalized_id,
        "criteria": normalized_criteria,
        "acceptance_digest": acceptance_digest(normalized_id, normalized_criteria),
        "sealed_at": (clock or (lambda: datetime.now(UTC)))().isoformat(),
    }
    for field, url in (("adr_url", adr_url), ("issue_url", issue_url)):
        if url is None:
            continue
        if not isinstance(url, str) or not _valid_https_url(url):
            return {"error": "url_not_https", "field": field, "url": url}
        receipt[field] = url
    return receipt


def verify_receipt(payload: Mapping[str, Any]) -> dict[str, object]:
    """Verify AcceptanceReceipt digest rules offline (ADR 0009 section 5)."""
    required = ("acceptance_id", "criteria", "acceptance_digest", "sealed_at")
    missing = [key for key in required if key not in payload]
    if missing:
        return {"verified": False, "error": "missing_fields", "missing": missing}

    acceptance_id = payload["acceptance_id"]
    criteria = payload["criteria"]
    digest = payload["acceptance_digest"]
    if not isinstance(acceptance_id, str):
        return {"verified": False, "error": "invalid_acceptance_id_type"}
    if not isinstance(criteria, list):
        return {"verified": False, "error": "invalid_criteria_type"}
    if not isinstance(digest, str):
        return {"verified": False, "error": "invalid_digest_type"}

    normalized_id = unicodedata.normalize("NFC", acceptance_id.strip())
    if not normalized_id or len(normalized_id) > MAX_ACCEPTANCE_ID_LEN:
        return {"verified": False, "error": "acceptance_id_invalid"}
    if not criteria:
        return {"verified": False, "error": "criteria_empty"}
    if len(criteria) > MAX_CRITERIA:
        return {"verified": False, "error": "criteria_too_many"}

    normalized_criteria: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(criteria):
        parsed = _parse_criterion(raw, index)
        if "error" in parsed:
            return {"verified": False, **{k: v for k, v in parsed.items() if k != "index"}}
        criterion_id = str(parsed["id"])
        if criterion_id in seen_ids:
            return {"verified": False, "error": "duplicate_criterion_id", "id": criterion_id}
        seen_ids.add(criterion_id)
        normalized_criteria.append(parsed)

    expected = acceptance_digest(normalized_id, normalized_criteria)
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


def _parse_criterion(raw: object, index: int) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {"error": "criterion_not_object", "index": index}
    if set(raw) - {"id", "statement", "verify"}:
        return {"error": "criterion_unknown_fields", "index": index}

    criterion_id = raw.get("id")
    statement = raw.get("statement")
    verify = raw.get("verify")

    if not isinstance(criterion_id, str):
        return {"error": "criterion_id_invalid", "index": index}
    normalized_id = unicodedata.normalize("NFC", criterion_id.strip())
    if not normalized_id or len(normalized_id) > MAX_CRITERION_ID_LEN:
        return {"error": "criterion_id_invalid", "index": index}
    if not _CRITERION_ID_RE.fullmatch(normalized_id):
        return {"error": "criterion_id_invalid", "index": index, "id": normalized_id}

    if not isinstance(statement, str):
        return {"error": "statement_invalid", "index": index}
    normalized_statement = unicodedata.normalize("NFC", statement)
    statement_bytes = normalized_statement.encode("utf-8")
    if not normalized_statement:
        return {"error": "statement_empty", "index": index}
    if len(statement_bytes) > MAX_STATEMENT_BYTES:
        return {"error": "statement_too_large", "index": index}

    parsed_verify = _parse_verify_ref(verify, index)
    if "error" in parsed_verify:
        return parsed_verify

    return {
        "id": normalized_id,
        "statement": normalized_statement,
        "verify": parsed_verify,
    }


def _parse_verify_ref(raw: object, index: int) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {"error": "verify_invalid", "index": index}
    if set(raw) - {"kind", "ref", "expect"}:
        return {"error": "verify_unknown_fields", "index": index}

    kind = raw.get("kind")
    ref = raw.get("ref")
    expect = raw.get("expect")

    if not isinstance(kind, str) or kind not in VERIFY_KINDS:
        return {"error": "verify_kind_invalid", "index": index, "kind": kind}
    if not isinstance(ref, str):
        return {"error": "verify_ref_invalid", "index": index}
    normalized_ref = unicodedata.normalize("NFC", ref)
    if not normalized_ref or len(normalized_ref.encode("utf-8")) > MAX_VERIFY_REF_LEN:
        return {"error": "verify_ref_invalid", "index": index}

    verify: dict[str, object] = {"kind": kind, "ref": normalized_ref}
    if expect is not None:
        if not isinstance(expect, str):
            return {"error": "verify_expect_invalid", "index": index}
        normalized_expect = unicodedata.normalize("NFC", expect)
        if len(normalized_expect.encode("utf-8")) > MAX_VERIFY_EXPECT_LEN:
            return {"error": "verify_expect_invalid", "index": index}
        verify["expect"] = normalized_expect
    return verify


def _valid_https_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.netloc)
