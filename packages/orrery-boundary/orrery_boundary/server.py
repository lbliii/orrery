"""Stdio MCP server for optional locality tools (Cursor / Claude Code)."""

from __future__ import annotations

from typing import Any

from orrery_boundary.export import export_at_ref
from orrery_boundary.grant import POLICY_EXPLICIT_PATHS
from orrery_boundary.witness import witness_approve

TOOL_NAMES = ("local/export-at-ref", "local/witness-approve")


def local_export_at_ref(
    ref: str,
    repo_root: str | None = None,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    return export_at_ref(ref, repo_root=repo_root, paths=paths)


def local_witness_approve(
    allowed_paths: list[str],
    policy: str = POLICY_EXPLICIT_PATHS,
    key_id: str | None = None,
) -> dict[str, Any]:
    return witness_approve(allowed_paths, policy=policy, key_id=key_id)


def build_mcp() -> Any:
    """Build the FastMCP app (requires the ``mcp`` package at runtime)."""
    from mcp.server.fastmcp import FastMCP

    app = FastMCP(
        "orrery-boundary",
        instructions=(
            "Optional locality adapter for Orrery protocol stars. "
            "local/export-at-ref inventories a git SHA into manifest-bind file rows; "
            "local/witness-approve signs a write-authority witness envelope. "
            "Hosted Orrery seals/verifies; this package is not registered in the "
            "hosted agent-card registry (locality: hybrid)."
        ),
    )

    @app.tool(
        name="local/export-at-ref",
        description=(
            "Export tracked files at a git SHA into {files:[{path,sha256,size}]} "
            "compatible with hosted orrery/manifest-bind. Locality: hybrid."
        ),
    )
    def _export(
        ref: str,
        repo_root: str | None = None,
        paths: list[str] | None = None,
    ) -> dict[str, Any]:
        return local_export_at_ref(ref, repo_root=repo_root, paths=paths)

    @app.tool(
        name="local/witness-approve",
        description=(
            "Operator-approve a Chirp Envelope witness whose payload includes "
            "grant_digest and allowed_paths for hosted orrery/write-authority-check. "
            "Locality: hybrid."
        ),
    )
    def _witness(
        allowed_paths: list[str],
        policy: str = POLICY_EXPLICIT_PATHS,
        key_id: str | None = None,
    ) -> dict[str, Any]:
        return local_witness_approve(allowed_paths, policy=policy, key_id=key_id)

    return app


def main() -> None:
    build_mcp().run(transport="stdio")


if __name__ == "__main__":
    main()
