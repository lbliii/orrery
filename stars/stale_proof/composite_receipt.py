"""Composite receipt cite helpers for constellation seals (ADR 0006/0007)."""

from __future__ import annotations

import re
from typing import Any

_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def normalize_cites(cites: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Validate and normalize ``decision_digest`` cites for composite receipts."""
    if not cites:
        return ()
    out: list[str] = []
    for digest in cites:
        if not isinstance(digest, str):
            msg = f"cites entry must be str, got {type(digest)!r}"
            raise TypeError(msg)
        lowered = digest.lower()
        if not _HEX_SHA256.match(lowered):
            msg = f"invalid decision_digest cite: {digest!r}"
            raise ValueError(msg)
        out.append(lowered)
    return tuple(out)


def with_cites(receipt: dict[str, Any], cites: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """Return composite receipt copy with validated ``cites`` array (ADR 0006 §3)."""
    normalized = normalize_cites(cites)
    if not normalized:
        return dict(receipt)
    merged = dict(receipt)
    merged["cites"] = list(normalized)
    return merged


def normalize_acceptance_cites(
    acceptance_cites: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    """Validate and normalize ``acceptance_digest`` cites for composite receipts."""
    if not acceptance_cites:
        return ()
    out: list[str] = []
    for digest in acceptance_cites:
        if not isinstance(digest, str):
            msg = f"acceptance_cites entry must be str, got {type(digest)!r}"
            raise TypeError(msg)
        lowered = digest.lower()
        if not _HEX_SHA256.match(lowered):
            msg = f"invalid acceptance_digest cite: {digest!r}"
            raise ValueError(msg)
        out.append(lowered)
    return tuple(out)


def with_acceptance_cites(
    receipt: dict[str, Any],
    acceptance_cites: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Return composite receipt copy with validated ``acceptance_cites`` (ADR 0009 §6)."""
    normalized = normalize_acceptance_cites(acceptance_cites)
    if not normalized:
        return dict(receipt)
    merged = dict(receipt)
    merged["acceptance_cites"] = list(normalized)
    return merged
