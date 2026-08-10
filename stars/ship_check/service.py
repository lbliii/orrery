"""Ship-check constellation — metadata-only and content-bundle modes (#214)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from stars.link_check_bounded.contract import DEFAULT_MAX_LINK_COUNT
from stars.link_check_bounded.service import Transport
from stars.manifest_preflight.contract import POLICY_DOCS_ONLY
from stars.npm_release.service import get as npm_get
from stars.pypi_release.service import get as pypi_get
from stars.source_watch.service import diff as source_diff
from stars.world_time.service import fetch_live_utc

CONSTELLATION = "orrery/ship-check"
MODE_METADATA = "metadata"
MODE_CONTENT_BUNDLE = "content-bundle"
MODES = frozenset({MODE_METADATA, MODE_CONTENT_BUNDLE})

PYPI = frozenset({"httpx", "pydantic"})
NPM = frozenset({"zod", "@modelcontextprotocol/sdk"})

_CONTENT_COMPONENTS = (
    {"name": "orrery/manifest-bind", "version": "0.1.0"},
    {"name": "orrery/manifest-preflight", "version": "0.1.0"},
    {"name": "orrery/structure-audit", "version": "0.1.0"},
    {"name": "orrery/link-check-bounded", "version": "0.1.0"},
)
_METADATA_LIMITATIONS = (
    "Metadata-only mode: release + source-watch + UTC; never deploy approval.",
    "Synchronous only — pause_policy.allowed is false (ADR 0007).",
    "Composite seal is in-package (no orrery/artifact-seal star).",
)
_CONTENT_LIMITATIONS = (
    "Content-bundle mode reuses content-readiness stage vocabulary (#213).",
    "Synchronous only — pause_policy.allowed is false (ADR 0007).",
    "Read-only assessment; no write-authority or patch stages.",
    "Composite seal is in-package (no orrery/artifact-seal star).",
)


def run(
    package: str = "",
    source_digest: str = "",
    *,
    mode: str = MODE_METADATA,
    files: object = None,
    policy: object = POLICY_DOCS_ONLY,
    max_link_count: object = DEFAULT_MAX_LINK_COUNT,
    package_provider: Callable[[str], dict[str, object]] | None = None,
    source_provider: Callable[[str], dict[str, object]] | None = None,
    world_time_provider: Callable[[], dict[str, object]] | None = None,
    link_transport: Transport | None = None,
) -> dict[str, object]:
    """Run ship-check in ``metadata`` (default) or ``content-bundle`` mode.

    Mode is selected via run input. Metadata mode keeps the historical
    package / source_digest contract. Content-bundle mode reuses the
    content-readiness stage vocabulary over a caller-supplied files bundle.
    """
    selected = MODE_METADATA if mode in ("", None) else str(mode)
    if selected not in MODES:
        return _seal(
            mode=selected,
            disposition="inconclusive",
            stages={"mode": {"error": "mode_invalid", "mode": selected}},
            components=[],
            limitations=("Unknown mode; use metadata or content-bundle.",),
            live_at_call=False,
            extra={"verdict": "incomplete"},
        )
    if selected == MODE_CONTENT_BUNDLE:
        return _run_content_bundle(
            files,
            policy=policy,
            max_link_count=max_link_count,
            link_transport=link_transport,
        )
    return _run_metadata(
        package,
        source_digest,
        package_provider=package_provider,
        source_provider=source_provider,
        world_time_provider=world_time_provider,
    )


def _run_metadata(
    package: str,
    source_digest: str,
    *,
    package_provider: Callable[[str], dict[str, object]] | None,
    source_provider: Callable[[str], dict[str, object]] | None,
    world_time_provider: Callable[[], dict[str, object]] | None,
) -> dict[str, object]:
    if package not in PYPI | NPM:
        return {
            "error": "package_not_allowed",
            "package": package,
            "live_at_call": True,
            "constellation": CONSTELLATION,
            "mode": MODE_METADATA,
        }
    package_result = (package_provider or _package)(package)
    source_result = (
        source_provider or (lambda digest: source_diff("python-release-notes", digest))
    )(source_digest)
    utc = (world_time_provider or fetch_live_utc)()
    complete = all("error" not in result for result in (package_result, source_result, utc))
    verdict = "ready_to_reason" if complete else "incomplete"
    disposition = "ready" if complete else "not-ready"
    components = [
        {
            "name": "orrery/pypi-release" if package in PYPI else "orrery/npm-release",
            "version": "0.1.0",
        },
        {"name": "orrery/source-watch", "version": "0.1.0"},
        {"name": "orrery/world-time", "version": "0.1.0"},
    ]
    stages = {
        "release": package_result,
        "source-watch": source_result,
        "world-time": utc,
    }
    return _seal(
        mode=MODE_METADATA,
        disposition=disposition,
        stages=stages,
        components=components,
        limitations=_METADATA_LIMITATIONS,
        live_at_call=True,
        extra={
            "verdict": verdict,
            "scope": "release metadata + fixed Python release notes + UTC evidence",
            "limitation": "This is not a deployment approval and has no side effects.",
            "package": package_result,
            "source_watch": source_result,
            "utc": utc,
        },
    )


def _run_content_bundle(
    files: object,
    *,
    policy: object,
    max_link_count: object,
    link_transport: Transport | None,
) -> dict[str, object]:
    from stars.content_readiness.service import run as content_readiness_run

    kwargs: dict[str, Any] = {}
    if link_transport is not None:
        kwargs["link_transport"] = link_transport
    result = content_readiness_run(files, policy, max_link_count, **kwargs)
    stages = result.get("stages")
    if not isinstance(stages, Mapping):
        stages = {"bundle": {"error": "stages_missing"}}
    return _seal(
        mode=MODE_CONTENT_BUNDLE,
        disposition=str(result.get("disposition", "inconclusive")),
        stages=dict(stages),
        components=list(_CONTENT_COMPONENTS),
        limitations=_CONTENT_LIMITATIONS,
        live_at_call=bool(result.get("live_at_call")),
    )


def _seal(
    *,
    mode: str,
    disposition: str,
    stages: Mapping[str, object],
    components: list[dict[str, object]] | tuple[dict[str, object], ...],
    limitations: tuple[str, ...] | list[str],
    live_at_call: bool,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    policy_digest, release = _composite_identity()
    payload: dict[str, object] = {
        "constellation": CONSTELLATION,
        "mode": mode,
        "disposition": disposition,
        "chain": "signed-envelope-chain",
        "policy_digest": policy_digest,
        "release": release,
        "stages": dict(stages),
        "components": list(components),
        "limitations": list(limitations),
        "live_at_call": live_at_call,
    }
    if extra:
        payload.update(extra)
    return payload


def _composite_identity() -> tuple[str, dict[str, str]]:
    """Match ADR 0007 composite_receipt_fields from the frozen ship-check graph."""
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


def _package(package: str) -> dict[str, object]:
    return pypi_get(package) if package in PYPI else npm_get(package)
