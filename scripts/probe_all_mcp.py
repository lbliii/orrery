#!/usr/bin/env python3
"""Probe every public catalog star and constellation MCP endpoint.

Uses publish-corpus fixtures for allowlisted tool arguments only.  Offline mode
(default when no origin is configured) validates the probe matrix without
network I/O.  Set ``ORRERY_PROBE_ORIGIN`` or pass ``--origin`` for a live HTTPS
probe against production or staging.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stars._core.corpus import require_nonempty_corpus
from stars.builtins import builtin_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PROFILES = REPO_ROOT / "fixtures" / "migration" / "profiles"
DEFAULT_ORIGIN = "https://orrery.lol"

PROFILE_ID_TO_FILE: dict[str, str] = {
    "docs/myst-to-mdx-baseline": "docs_myst_to_mdx_baseline.json",
    "api-spec/openapi-3-0-to-3-1-safe": "api_spec_openapi_3_0_to_3_1_safe.json",
}


@dataclass(frozen=True, slots=True)
class ProbeCase:
    name: str
    path: str
    kind: str
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProbeSummary:
    ok: int
    fail: int
    skip: int
    total: int


def _load_migration_profile(profile_id: str) -> dict[str, Any]:
    filename = PROFILE_ID_TO_FILE.get(profile_id)
    if filename is None:
        msg = f"no fixture profile mapping for profile_id {profile_id!r}"
        raise ValueError(msg)
    path = MIGRATION_PROFILES / filename
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        msg = f"migration profile fixture must be an object: {path}"
        raise TypeError(msg)
    return loaded


def enrich_arguments(name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Hydrate repo fixtures where corpus args are intentionally abbreviated."""
    args = copy.deepcopy(dict(arguments))
    if name == "orrery/migration-git-handoff":
        profile = args.get("profile")
        if isinstance(profile, dict) and set(profile) == {"profile_id"}:
            profile_id = profile["profile_id"]
            if isinstance(profile_id, str):
                args["profile"] = _load_migration_profile(profile_id)
    return args


def build_probe_cases() -> tuple[ProbeCase, ...]:
    """Build one allowlisted probe per registered public star or constellation."""
    cases: list[ProbeCase] = []
    for definition in builtin_registry():
        corpus = require_nonempty_corpus(definition)
        prompt = corpus[0]
        cases.append(
            ProbeCase(
                name=definition.name,
                path=definition.direct_mcp_path,
                kind=definition.kind,
                tool=prompt.tool,
                arguments=enrich_arguments(definition.name, prompt.arguments or {}),
            )
        )
    return tuple(cases)


def _post_json(url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        status = getattr(response, "status", response.getcode())
        if status != 200:
            raise ValueError(f"unexpected HTTP status {status} for {url}")
        raw = json.loads(response.read())
    if not isinstance(raw, dict):
        raise ValueError(f"expected JSON object from {url}")
    return raw


def _wire_ok(wire: Mapping[str, Any]) -> bool:
    if wire.get("error"):
        return False
    result = wire.get("result")
    if not isinstance(result, Mapping):
        return False
    if result.get("isError"):
        return False
    content = result.get("content")
    return isinstance(content, list) and bool(content)


def probe_case(origin: str, case: ProbeCase) -> None:
    """Call one catalog MCP endpoint with corpus allowlisted arguments."""
    url = origin.rstrip("/") + case.path
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": case.tool, "arguments": case.arguments},
    }
    wire = _post_json(url, payload)
    if not _wire_ok(wire):
        detail = wire.get("error") or wire.get("result")
        raise ValueError(f"{case.name} {case.tool} failed: {detail!r}")


def run_offline() -> ProbeSummary:
    """Validate the full catalog probe matrix without network I/O."""
    cases = build_probe_cases()
    print(f"offline: {len(cases)} catalog entries with corpus-backed probes")
    for case in cases:
        print(f"  {case.kind:14} {case.name:40} {case.tool}")
    return ProbeSummary(ok=len(cases), fail=0, skip=0, total=len(cases))


def run_live(origin: str) -> ProbeSummary:
    """Probe every catalog MCP endpoint over HTTPS."""
    cases = build_probe_cases()
    ok = fail = skip = 0
    for case in cases:
        try:
            probe_case(origin, case)
        except urllib.error.HTTPError as error:
            fail += 1
            print(f"FAIL {case.name}: HTTP {error.code}", file=sys.stderr)
        except Exception as error:
            fail += 1
            print(f"FAIL {case.name}: {error}", file=sys.stderr)
        else:
            ok += 1
            print(f"OK   {case.name}")
    total = len(cases)
    print(f"ok: {ok}, fail: {fail}, skip: {skip}, total: {total}")
    if fail:
        raise SystemExit(1)
    return ProbeSummary(ok=ok, fail=fail, skip=skip, total=total)


def resolve_origin(explicit: str | None) -> str | None:
    if explicit:
        return explicit.rstrip("/")
    env_origin = os.environ.get("ORRERY_PROBE_ORIGIN", "").strip()
    return env_origin.rstrip("/") if env_origin else None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin",
        default=None,
        help="HTTPS origin for live probes (default env ORRERY_PROBE_ORIGIN, else offline)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Validate probe matrix locally without network I/O",
    )
    args = parser.parse_args(argv)
    origin = resolve_origin(args.origin)
    if args.offline or origin is None:
        summary = run_offline()
        print(
            f"ok: {summary.ok}, fail: {summary.fail}, "
            f"skip: {summary.skip}, total: {summary.total}"
        )
        return
    run_live(origin)


if __name__ == "__main__":
    main()
