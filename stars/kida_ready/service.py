"""Kida-ready composition — frozen check → gate → render subgraph (#403)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from stars.kida_check.service import check as kida_check
from stars.kida_render.service import render as kida_render

CONSTELLATION = "orrery/kida-ready"
DISPOSITIONS = ("ready", "needs-work", "inconclusive")
_COMPONENTS = (
    {"name": "orrery/kida-check", "version": "0.1.0"},
    {"name": "orrery/kida-render", "version": "0.1.0"},
)
_LIMITATIONS = (
    "Synchronous only — pause_policy.allowed is false (ADR 0007).",
    "Render runs only when kida-check passes the internal gate.",
    "Single-template render uses the first sorted template from the bundle.",
    "Composite seal is in-package (no orrery/artifact-seal star).",
)


def run(
    templates: object,
    data: object,
    *,
    validate_calls: bool = True,
    strict: bool = False,
    surface: str = "html",
) -> dict[str, object]:
    """Run kida-check → gate → kida-render and seal a composite disposition."""
    check_result = kida_check(
        templates,
        validate_calls=validate_calls,
        strict=strict,
    )
    if "error" in check_result:
        return _seal(
            disposition="inconclusive",
            stages={"kida-check": check_result},
        )

    stages: dict[str, object] = {"kida-check": check_result}
    if not bool(check_result.get("passed")):
        stages["gate"] = {
            "passed": False,
            "status": "blocked",
            "reason": "kida-check findings",
        }
        return _seal(disposition="needs-work", stages=stages)

    stages["gate"] = {"passed": True, "status": "open"}

    template_for_render = _render_template(templates)
    if template_for_render is None:
        return _seal(
            disposition="inconclusive",
            stages={
                **stages,
                "kida-render": {"error": "template_unavailable"},
            },
        )

    render_result = kida_render(template_for_render, data, surface=surface)
    stages["kida-render"] = render_result
    if "error" in render_result:
        return _seal(disposition="inconclusive", stages=stages)

    return _seal(disposition="ready", stages=stages)


def _render_template(templates: object) -> str | Mapping[str, object] | None:
    if isinstance(templates, list) and templates:
        first = templates[0]
        if isinstance(first, Mapping):
            path = first.get("path")
            content = first.get("content")
            if isinstance(path, str) and isinstance(content, str):
                return {"path": path, "content": content}
        if isinstance(first, str) and first:
            return first
    return None


def _seal(
    *,
    disposition: str,
    stages: Mapping[str, object],
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
