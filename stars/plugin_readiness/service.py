"""Sync plugin-readiness composition over protocol stars (ADR 0007)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from stars.manifest_bind.service import bind as manifest_bind
from stars.plugin_preflight.contract import PROFILE_V1
from stars.plugin_preflight.service import check as plugin_preflight
from stars.structure_audit.service import audit as structure_audit

CONSTELLATION = "orrery/plugin-readiness"
DISPOSITIONS = ("conformant", "needs-work", "inconclusive")
_COMPONENTS = (
    {"name": "orrery/manifest-bind", "version": "0.1.0"},
    {"name": "orrery/plugin-preflight", "version": "0.1.0"},
    {"name": "orrery/structure-audit", "version": "0.1.0"},
)
_LIMITATIONS = (
    "Synchronous only — pause_policy.allowed is false (ADR 0007).",
    "Read-only assessment; does not install or launch plugins.",
    "Composite seal is in-package (no orrery/artifact-seal star).",
    "structure-audit runs only on discovered skills/*/SKILL.md files.",
)


def run(files: object) -> dict[str, object]:
    """Run the frozen plugin-readiness subgraph and seal a disposition."""
    parsed, parse_error = _parse_bundle(files)
    if parse_error is not None:
        return _seal(
            disposition="inconclusive",
            stages={"bundle": parse_error},
        )

    assert parsed is not None
    inventory = _inventory_rows(parsed)
    content_files = [{"path": row["path"], "content": row["content"]} for row in parsed]

    bound = manifest_bind(inventory)
    if "error" in bound:
        return _seal(disposition="inconclusive", stages={"manifest-bind": bound})

    preflight = plugin_preflight(
        content_files,
        PROFILE_V1,
        manifest_digest=bound.get("manifest_digest"),
    )
    if "error" in preflight:
        return _seal(
            disposition="inconclusive",
            stages={"manifest-bind": bound, "plugin-preflight": preflight},
        )

    skill_files = [
        {"path": row["path"], "content": row["content"]}
        for row in parsed
        if _is_skill_md(row["path"])
    ]
    if skill_files:
        structure = structure_audit(skill_files)
        if "error" in structure:
            return _seal(
                disposition="inconclusive",
                stages={
                    "manifest-bind": bound,
                    "plugin-preflight": preflight,
                    "structure-audit": structure,
                },
            )
    else:
        structure = {
            "skipped": True,
            "reason": "no_skills",
            "passed": True,
            "findings": [],
            "finding_codes": [],
        }

    stages = {
        "manifest-bind": bound,
        "plugin-preflight": preflight,
        "structure-audit": structure,
    }
    evaluative_ok = bool(preflight.get("passed")) and bool(structure.get("passed"))
    disposition = "conformant" if evaluative_ok else "needs-work"
    return _seal(disposition=disposition, stages=stages)


def _seal(*, disposition: str, stages: Mapping[str, object]) -> dict[str, object]:
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
        "live_at_call": False,
    }


def _composite_identity() -> tuple[str, dict[str, str]]:
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
        if set(raw) - {"path", "content"}:
            return None, {"error": "entry_unknown_fields", "index": index}
        path = raw.get("path")
        content = raw.get("content")
        if not isinstance(path, str) or not path:
            return None, {"error": "path_invalid", "index": index}
        if not isinstance(content, str):
            return None, {"error": "content_invalid", "path": path, "index": index}
        if path in seen:
            return None, {"error": "duplicate_path", "path": path, "index": index}
        seen.add(path)
        parsed.append({"path": path, "content": content})
    return parsed, None


def _inventory_rows(parsed: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in parsed:
        raw = entry["content"].encode()
        rows.append(
            {
                "path": entry["path"],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
            }
        )
    return rows


def _is_skill_md(path: str) -> bool:
    parts = path.split("/")
    return len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md"
