"""Compare source inventory to target inventory for semantic-loss evidence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .contract import MAX_DIFF_ROWS, MAX_MESSAGE_BYTES, SEMANTIC_EQUIVALENTS


def build_migration_diff(
    *,
    source_findings: Sequence[Mapping[str, Any]],
    target_constructs: Sequence[Mapping[str, object]],
    file_entries: Sequence[Mapping[str, Any]],
    source_paths: set[str],
    target_paths: set[str],
    link_asset_report: Mapping[str, Any] | None,
    build_status: Mapping[str, Any],
) -> dict[str, object]:
    """Emit bounded migration-diff evidence (not a runtime compatibility claim)."""
    source_by_path = _feature_counts_by_path(source_findings)
    target_index = {
        (str(row["path"]), str(row["feature_id"])): int(row["count"])
        for row in target_constructs
    }

    dropped: list[dict[str, object]] = []
    added: list[dict[str, object]] = []

    for path, features in sorted(source_by_path.items()):
        for feature_id, count in sorted(features.items()):
            equivalents = SEMANTIC_EQUIVALENTS.get(feature_id)
            if equivalents is None:
                # Unsupported / decision_required / other: loss only if vanished
                # entirely from residual MyST scan counts on the same path.
                residual = target_index.get((path, feature_id), 0)
                if residual == 0 and feature_id.startswith("myst."):
                    dropped.append(
                        {
                            "kind": "dropped_construct",
                            "path": path,
                            "feature_id": feature_id,
                            "source_count": count,
                            "target_count": 0,
                            "message": "source construct absent from target",
                        }
                    )
                continue

            target_count = sum(
                target_index.get((path, equiv), 0) for equiv in equivalents
            )
            if target_count == 0:
                dropped.append(
                    {
                        "kind": "dropped_construct",
                        "path": path,
                        "feature_id": feature_id,
                        "source_count": count,
                        "target_count": 0,
                        "message": "semantic equivalent missing after transform",
                    }
                )

    # Added: target-only MDX components with no source equivalent on path.
    for (path, feature_id), count in sorted(target_index.items()):
        if feature_id != "mdx.component.admonition":
            continue
        source_admonitions = source_by_path.get(path, {}).get(
            "myst.directive.admonition", 0
        )
        if source_admonitions == 0:
            added.append(
                {
                    "kind": "added_construct",
                    "path": path,
                    "feature_id": feature_id,
                    "source_count": 0,
                    "target_count": count,
                    "message": "MDX admonition without source directive",
                }
            )

    unresolved_links, unresolved_assets = _unresolved_from_report(link_asset_report)

    mapped_paths = {
        str(item["path"])
        for item in file_entries
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    }
    expected_paths = sorted(source_paths)
    missing_mapping = [path for path in expected_paths if path not in mapped_paths]
    extra_targets = sorted(target_paths - source_paths)

    mapping_coverage = {
        "expected_count": len(expected_paths),
        "covered_count": len(expected_paths) - len(missing_mapping),
        "missing_paths": missing_mapping[:MAX_DIFF_ROWS],
        "extra_target_paths": extra_targets[:MAX_DIFF_ROWS],
        "complete": not missing_mapping,
    }

    truncated = False
    if len(dropped) > MAX_DIFF_ROWS:
        dropped = dropped[:MAX_DIFF_ROWS]
        truncated = True
    if len(added) > MAX_DIFF_ROWS:
        added = added[:MAX_DIFF_ROWS]
        truncated = True
    if len(unresolved_links) > MAX_DIFF_ROWS:
        unresolved_links = unresolved_links[:MAX_DIFF_ROWS]
        truncated = True
    if len(unresolved_assets) > MAX_DIFF_ROWS:
        unresolved_assets = unresolved_assets[:MAX_DIFF_ROWS]
        truncated = True

    return {
        "build_status": {
            "passed": bool(build_status.get("passed")),
            "finding_count": len(list(build_status.get("findings") or [])),
        },
        "dropped_constructs": dropped,
        "added_constructs": added,
        "unresolved_links": unresolved_links,
        "unresolved_assets": unresolved_assets,
        "mapping_coverage": mapping_coverage,
        "truncated": truncated,
    }


def semantic_loss_findings(diff: Mapping[str, Any]) -> list[dict[str, object]]:
    """Turn migration-diff rows into ADR finding records (visible even if build passes)."""
    findings: list[dict[str, object]] = []
    for row in diff.get("dropped_constructs") or []:
        findings.append(
            {
                "feature_id": str(row.get("feature_id", "migration.semantic_loss")),
                "class": "decision_required",
                "path": str(row.get("path", "")),
                "severity": "informational",
                "action": "report",
                "message": _bound_message(
                    f"dropped:{row.get('message', 'semantic loss')}"
                ),
            }
        )
    for row in diff.get("added_constructs") or []:
        findings.append(
            {
                "feature_id": str(row.get("feature_id", "migration.semantic_add")),
                "class": "decision_required",
                "path": str(row.get("path", "")),
                "severity": "informational",
                "action": "report",
                "message": _bound_message(
                    f"added:{row.get('message', 'unexpected construct')}"
                ),
            }
        )
    for row in diff.get("unresolved_links") or []:
        findings.append(
            {
                "feature_id": "md.link.unresolved",
                "class": "decision_required",
                "path": str(row.get("path", "")),
                "severity": "informational",
                "action": "report",
                "message": _bound_message(str(row.get("target", "unresolved link"))),
            }
        )
    for row in diff.get("unresolved_assets") or []:
        findings.append(
            {
                "feature_id": "md.asset.unresolved",
                "class": "decision_required",
                "path": str(row.get("path", "")),
                "severity": "informational",
                "action": "report",
                "message": _bound_message(str(row.get("target", "unresolved asset"))),
            }
        )
    coverage = diff.get("mapping_coverage")
    if isinstance(coverage, Mapping) and not coverage.get("complete", True):
        for path in coverage.get("missing_paths") or []:
            findings.append(
                {
                    "feature_id": "migration.mapping.coverage",
                    "class": "decision_required",
                    "path": str(path),
                    "severity": "informational",
                    "action": "report",
                    "message": "source path missing from change_bundle mapping",
                }
            )
    return findings


def _feature_counts_by_path(
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Counter[str]]:
    by_path: dict[str, Counter[str]] = {}
    for item in findings:
        path = str(item.get("path", ""))
        feature_id = str(item.get("feature_id", ""))
        if not path or not feature_id:
            continue
        by_path.setdefault(path, Counter())[feature_id] += 1
    return by_path


def _unresolved_from_report(
    report: Mapping[str, Any] | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    links: list[dict[str, object]] = []
    assets: list[dict[str, object]] = []
    if not isinstance(report, Mapping):
        return links, assets
    rows = report.get("links")
    if not isinstance(rows, list):
        return links, assets
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("status", ""))
        if status not in {"unresolved", "unsupported", "unsafe"}:
            continue
        payload = {
            "path": str(row.get("path", "")),
            "target": str(row.get("after") or row.get("before") or ""),
            "status": status,
        }
        if row.get("kind") == "asset":
            assets.append(payload)
        else:
            links.append(payload)
    return links, assets


def _bound_message(message: str) -> str:
    raw = message.encode("utf-8")
    if len(raw) <= MAX_MESSAGE_BYTES:
        return message
    return raw[:MAX_MESSAGE_BYTES].decode("utf-8", "ignore")
