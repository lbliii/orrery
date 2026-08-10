"""Sync authorized-content-patch composition (#215).

Frozen planner subgraph: readiness gates (via content-readiness reuse) →
write-authority-check → patch-capture → in-package composite seal.
Never applies patches to the caller filesystem.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from stars.content_readiness.service import run as content_readiness_run
from stars.link_check_bounded.contract import DEFAULT_MAX_LINK_COUNT
from stars.link_check_bounded.service import Transport
from stars.manifest_preflight.contract import POLICY_DOCS_ONLY
from stars.patch_capture.service import capture as patch_capture
from stars.write_authority_check.service import check as write_authority_check

CONSTELLATION = "orrery/authorized-content-patch"
DISPOSITIONS = ("authorized", "denied", "needs-work", "inconclusive")
_COMPONENTS = (
    {"name": "orrery/manifest-bind", "version": "0.1.0"},
    {"name": "orrery/manifest-preflight", "version": "0.1.0"},
    {"name": "orrery/structure-audit", "version": "0.1.0"},
    {"name": "orrery/link-check-bounded", "version": "0.1.0"},
    {"name": "orrery/write-authority-check", "version": "0.1.0"},
    {"name": "orrery/patch-capture", "version": "0.1.0"},
)
_LIMITATIONS = (
    "Synchronous only — pause_policy.allowed is false (ADR 0007).",
    "Does not apply patches to the caller filesystem.",
    "Composite seal is in-package (no orrery/artifact-seal star).",
    "Readiness reuses orrery/content-readiness stage vocabulary (#213).",
    "Publication / deploy is out of scope (see orrery/publish-gate).",
)


def run(
    before: object,
    after: object,
    authority: object,
    policy: object = POLICY_DOCS_ONLY,
    max_link_count: object = DEFAULT_MAX_LINK_COUNT,
    *,
    link_transport: Transport | None = None,
) -> dict[str, object]:
    """Run the frozen authorized-content-patch subgraph and seal a disposition.

    Caller supplies before/after content bundles and an explicit write grant.
    Digests are derived in-process from content bytes — Orrery never opens a
    repository and never writes caller files.
    """
    after_parsed, after_error = _parse_bundle(after, side="after")
    if after_error is not None:
        return _seal(disposition="inconclusive", stages={"bundle": after_error})

    before_parsed, before_error = _parse_bundle(before, side="before")
    if before_error is not None:
        return _seal(disposition="inconclusive", stages={"bundle": before_error})

    assert after_parsed is not None and before_parsed is not None

    readiness_kwargs: dict[str, Any] = {}
    if link_transport is not None:
        readiness_kwargs["link_transport"] = link_transport
    readiness = content_readiness_run(
        after_parsed,
        policy,
        max_link_count,
        **readiness_kwargs,
    )
    readiness_stages = readiness.get("stages")
    if not isinstance(readiness_stages, Mapping):
        readiness_stages = {"bundle": {"error": "stages_missing"}}
    stages: dict[str, object] = dict(readiness_stages)

    readiness_disposition = str(readiness.get("disposition", "inconclusive"))
    if readiness_disposition == "inconclusive":
        return _seal(
            disposition="inconclusive",
            stages=stages,
            live_at_call=bool(readiness.get("live_at_call")),
        )
    if readiness_disposition != "ready":
        return _seal(
            disposition="needs-work",
            stages=stages,
            live_at_call=bool(readiness.get("live_at_call")),
        )

    bound = readiness_stages.get("manifest-bind")
    manifest_digest = (
        bound.get("manifest_digest") if isinstance(bound, Mapping) else None
    )
    if not isinstance(manifest_digest, str) or not manifest_digest:
        return _seal(
            disposition="inconclusive",
            stages={
                **stages,
                "write-authority-check": {"error": "manifest_digest_missing"},
            },
            live_at_call=bool(readiness.get("live_at_call")),
        )

    authority_result = write_authority_check(manifest_digest, authority)
    stages["write-authority-check"] = authority_result
    if "error" in authority_result:
        return _seal(
            disposition="inconclusive",
            stages=stages,
            live_at_call=bool(readiness.get("live_at_call")),
        )
    if not bool(authority_result.get("authorized")):
        return _seal(
            disposition="denied",
            stages=stages,
            live_at_call=bool(readiness.get("live_at_call")),
        )

    before_snap = _snapshot_from_parsed(before_parsed)
    after_snap = _snapshot_from_parsed(after_parsed)
    patch = patch_capture(before_snap, after_snap)
    stages["patch-capture"] = patch
    if "error" in patch:
        return _seal(
            disposition="inconclusive",
            stages=stages,
            live_at_call=bool(readiness.get("live_at_call")),
        )

    allowed = authority_result.get("allowed_paths")
    changed = patch.get("changed_paths")
    if isinstance(allowed, list) and isinstance(changed, list):
        allowed_set = {str(path) for path in allowed}
        uncovered = sorted(
            str(path) for path in changed if str(path) not in allowed_set
        )
        if uncovered:
            stages["path-grant"] = {
                "authorized": False,
                "codes": ["path_not_granted"],
                "uncovered_paths": uncovered,
            }
            return _seal(
                disposition="denied",
                stages=stages,
                live_at_call=bool(readiness.get("live_at_call")),
            )

    return _seal(
        disposition="authorized",
        stages=stages,
        live_at_call=bool(readiness.get("live_at_call")),
    )


def _seal(
    *,
    disposition: str,
    stages: Mapping[str, object],
    live_at_call: bool = False,
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
    *,
    side: str,
) -> tuple[list[dict[str, str]] | None, dict[str, object] | None]:
    if not isinstance(files, list):
        return None, {"error": "files_invalid", "side": side}
    # Empty before is valid (all-new content); empty after is not.
    if side == "after" and not files:
        return None, {"error": "files_invalid", "side": side}
    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(files):
        if not isinstance(raw, Mapping):
            return None, {"error": "entry_not_object", "side": side, "index": index}
        unknown = set(raw) - {"path", "content", "format"}
        if unknown:
            return None, {
                "error": "entry_unknown_fields",
                "side": side,
                "index": index,
            }
        path = raw.get("path")
        content = raw.get("content")
        fmt = raw.get("format", "markdown")
        if not isinstance(path, str) or not path:
            return None, {"error": "path_invalid", "side": side, "index": index}
        if not isinstance(content, str):
            return None, {
                "error": "content_invalid",
                "side": side,
                "path": path,
                "index": index,
            }
        if fmt not in {"markdown", "html"}:
            return None, {
                "error": "format_invalid",
                "side": side,
                "path": path,
                "index": index,
            }
        if path in seen:
            return None, {
                "error": "duplicate_path",
                "side": side,
                "path": path,
                "index": index,
            }
        seen.add(path)
        entry: dict[str, str] = {"path": path, "content": content}
        if "format" in raw:
            entry["format"] = str(fmt)
        parsed.append(entry)
    return parsed, None


def _snapshot_from_parsed(parsed: Sequence[Mapping[str, str]]) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for entry in parsed:
        content = entry["content"]
        raw = content.encode()
        files.append(
            {
                "path": entry["path"],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
                "content": content,
            }
        )
    return {"files": files}
