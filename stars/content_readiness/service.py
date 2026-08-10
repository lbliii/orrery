"""Sync content-readiness composition over protocol stars (ADR 0007 Example 1)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from stars.link_check_bounded.contract import DEFAULT_MAX_LINK_COUNT
from stars.link_check_bounded.service import Transport
from stars.link_check_bounded.service import check as link_check
from stars.manifest_bind.service import bind as manifest_bind
from stars.manifest_preflight.contract import POLICY_DOCS_ONLY
from stars.manifest_preflight.service import check as manifest_preflight
from stars.structure_audit.service import audit as structure_audit

CONSTELLATION = "orrery/content-readiness"
DISPOSITIONS = ("ready", "needs-work", "inconclusive")
_COMPONENTS = (
    {"name": "orrery/manifest-bind", "version": "0.1.0"},
    {"name": "orrery/manifest-preflight", "version": "0.1.0"},
    {"name": "orrery/structure-audit", "version": "0.1.0"},
    {"name": "orrery/link-check-bounded", "version": "0.1.0"},
)
_LIMITATIONS = (
    "Synchronous only — pause_policy.allowed is false (ADR 0007 Example 1).",
    "Read-only assessment; no write-authority or patch stages.",
    "Composite seal is in-package (no orrery/artifact-seal star).",
    "Link checks only HEAD allowlisted HTTPS origins.",
)


def run(
    files: object,
    policy: object = POLICY_DOCS_ONLY,
    max_link_count: object = DEFAULT_MAX_LINK_COUNT,
    *,
    link_transport: Transport | None = None,
) -> dict[str, object]:
    """Run the frozen content-readiness subgraph and seal a disposition.

    Caller supplies a content bundle (``path`` + ``content``, optional
    ``format``). Digests for manifest stages are derived in-process from
    content bytes — Orrery never opens a repository.
    """
    parsed, parse_error = _parse_bundle(files)
    if parse_error is not None:
        return _seal(
            disposition="inconclusive",
            stages={"bundle": parse_error},
            live_at_call=False,
        )

    assert parsed is not None
    inventory = _inventory_rows(parsed)
    content_files = [{"path": row["path"], "content": row["content"]} for row in parsed]
    link_files = [
        {
            "path": row["path"],
            "content": row["content"],
            **({"format": row["format"]} if "format" in row else {}),
        }
        for row in parsed
    ]

    bound = manifest_bind(inventory)
    if "error" in bound:
        return _seal(
            disposition="inconclusive",
            stages={"manifest-bind": bound},
            live_at_call=False,
        )

    preflight = manifest_preflight(
        inventory,
        policy,
        manifest_digest=bound.get("manifest_digest"),
    )
    if "error" in preflight:
        return _seal(
            disposition="inconclusive",
            stages={"manifest-bind": bound, "manifest-preflight": preflight},
            live_at_call=False,
        )

    structure = structure_audit(content_files)
    if "error" in structure:
        return _seal(
            disposition="inconclusive",
            stages={
                "manifest-bind": bound,
                "manifest-preflight": preflight,
                "structure-audit": structure,
            },
            live_at_call=False,
        )

    link_kwargs: dict[str, Any] = {}
    if link_transport is not None:
        link_kwargs["transport"] = link_transport
    links = link_check(link_files, max_link_count, **link_kwargs)
    if "error" in links:
        return _seal(
            disposition="inconclusive",
            stages={
                "manifest-bind": bound,
                "manifest-preflight": preflight,
                "structure-audit": structure,
                "link-check-bounded": links,
            },
            live_at_call=False,
        )

    stages = {
        "manifest-bind": bound,
        "manifest-preflight": preflight,
        "structure-audit": structure,
        "link-check-bounded": links,
    }
    evaluative_ok = (
        bool(preflight.get("passed"))
        and bool(structure.get("passed"))
        and bool(links.get("passed"))
    )
    disposition = "ready" if evaluative_ok else "needs-work"
    return _seal(
        disposition=disposition,
        stages=stages,
        live_at_call=bool(links.get("live_at_call")),
    )


def _seal(
    *,
    disposition: str,
    stages: Mapping[str, object],
    live_at_call: bool,
) -> dict[str, object]:
    policy_digest, release = _composite_identity()
    return {
        "constellation": CONSTELLATION,
        "disposition": disposition,
        "chain": "signed-envelope-chain",
        "policy_digest": policy_digest,
        "release": release,
        "stages": dict(stages),
        "components": list(_COMPONENTS),
        "limitations": list(_LIMITATIONS),
        "live_at_call": live_at_call,
    }


def _composite_identity() -> tuple[str, dict[str, str]]:
    """Match ADR 0007 composite_receipt_fields from the frozen policy graph."""
    from catalog.constellation import policy_for

    graph = policy_for(CONSTELLATION)
    if graph is None:
        return "sha256:missing-policy", {"digest": "sha256:missing", "key_id": "missing"}
    blob = json.dumps(
        {
            "constellation": CONSTELLATION,
            "nodes": [node.id for node in graph.nodes],
            "edges": [(edge.source, edge.target, edge.kind) for edge in graph.edges],
            "release": {
                "digest": graph.release_digest,
                "key_id": graph.release_key_id,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = "sha256:" + hashlib.sha256(blob.encode()).hexdigest()
    return digest, {"digest": graph.release_digest, "key_id": graph.release_key_id}


def _parse_bundle(
    files: object,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if not isinstance(files, list) or not files:
        return None, {"error": "files_invalid"}
    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(files):
        if not isinstance(raw, Mapping):
            return None, {"error": "entry_not_object", "index": index}
        unknown = set(raw) - {"path", "content", "format"}
        if unknown:
            return None, {"error": "entry_unknown_fields", "index": index}
        path = raw.get("path")
        content = raw.get("content")
        fmt = raw.get("format", "markdown")
        if not isinstance(path, str) or not path:
            return None, {"error": "path_invalid", "index": index}
        if not isinstance(content, str):
            return None, {"error": "content_invalid", "path": path, "index": index}
        if fmt not in {"markdown", "html"}:
            return None, {"error": "format_invalid", "path": path, "index": index}
        if path in seen:
            return None, {"error": "duplicate_path", "path": path, "index": index}
        seen.add(path)
        entry: dict[str, str] = {"path": path, "content": content}
        if "format" in raw:
            entry["format"] = str(fmt)
        parsed.append(entry)
    return parsed, None


def _inventory_rows(parsed: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in parsed:
        content = entry["content"]
        raw = content.encode()
        rows.append(
            {
                "path": entry["path"],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
            }
        )
    return rows
