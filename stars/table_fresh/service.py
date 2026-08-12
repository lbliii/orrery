"""Actual bounded csv-url -> table-diff constellation execution."""

from __future__ import annotations

from stars.csv_url.service import Fetch
from stars.csv_url.service import get as get_csv
from stars.table_diff.service import diff

from .contract import BASELINE_SCHEMA, EXAMPLE_BASELINE, INVALID_BASELINE_REMEDIATION


def run(baseline: object, *, csv_fetch: Fetch | None = None) -> dict[str, object]:
    """Freshen a bounded current sample then compare it to caller-held baseline."""
    current = get_csv("flights-airport", **({"fetch": csv_fetch} if csv_fetch else {}))
    if "error" in current:
        return {"error": "current_source_failed", "current": current, "scope": "bounded_sample"}
    if not isinstance(baseline, dict) or not isinstance(baseline.get("rows"), list):
        return _invalid_baseline()
    baseline_rows = _routes(baseline["rows"])
    current_rows = _routes(current["rows"])
    if baseline_rows is None or current_rows is None:
        return _invalid_baseline()
    left = {"rows": baseline_rows, "digest": baseline.get("source_digest", baseline.get("digest"))}
    right = {"rows": current_rows, "digest": current["source_digest"]}
    verdict = diff(left, right, "route")
    if "error" in verdict:
        return _invalid_baseline(detail=verdict.get("detail"))
    return {
        "constellation": "orrery/table-fresh",
        "scope": "bounded_sample",
        "limitation": "Comparison covers csv-url's current bounded 100-row sample only.",
        "components": [
            {"name": "orrery/csv-url", "version": "0.1.0"},
            {"name": "orrery/table-diff", "version": "0.1.0"},
        ],
        "current_source": {
            key: current[key]
            for key in (
                "source_url",
                "canonical_url",
                "status",
                "source_digest",
                "observed_at",
                "row_count",
                "rows_truncated",
            )
        },
        "current_rows_returned": len(current_rows),
        "sample_size_limit": 100,
        "baseline": verdict["left"],
        "current": verdict["right"],
        "diff": {
            key: verdict[key]
            for key in (
                "added_count",
                "removed_count",
                "changed_count",
                "unchanged_count",
                "added",
                "removed",
                "changed",
            )
        },
        "verdict": (
            "unchanged"
            if not any(verdict[key] for key in ("added_count", "removed_count", "changed_count"))
            else "changed"
        ),
        "live_at_call": True,
    }


def _invalid_baseline(**extra: object) -> dict[str, object]:
    item: dict[str, object] = {
        "error": "invalid_baseline",
        "scope": "bounded_sample",
        "remediation": INVALID_BASELINE_REMEDIATION,
        "expected_shape": BASELINE_SCHEMA,
        "example": EXAMPLE_BASELINE,
    }
    item.update(extra)
    return item


def _routes(rows: object) -> list[dict[str, object]] | None:
    if not isinstance(rows, list):
        return None
    result: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"origin", "destination", "count"}:
            return None
        origin, destination = row["origin"], row["destination"]
        if not isinstance(origin, str) or not isinstance(destination, str):
            return None
        result.append({"route": f"{origin}\u0000{destination}", "count": row["count"]})
    return result
