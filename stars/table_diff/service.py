"""Pure bounded diff of two caller-provided tabular snapshots."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

from .contract import (
    MAX_COLUMNS,
    MAX_EXAMPLES,
    MAX_INPUT_BYTES,
    MAX_ROWS,
    MAX_STRING_CHARS,
)


def diff(left: object, right: object, key_column: str) -> dict[str, object]:
    """Compare snapshots in memory without fetching or retaining caller data."""
    try:
        left_snapshot = _snapshot(left, "left")
        right_snapshot = _snapshot(right, "right")
        _validate_input_size(left_snapshot, right_snapshot)
        schema = _schema(left_snapshot["rows"], right_snapshot["rows"])
        _validate_key_column(key_column, schema)
        left_rows = _canonical_rows(left_snapshot["rows"], schema, key_column)
        right_rows = _canonical_rows(right_snapshot["rows"], schema, key_column)
    except ValueError as error:
        return {"error": "invalid_snapshot", "detail": str(error), "live_at_call": True}

    left_by_key = {_key_token(row[key_column]): row for row in left_rows}
    right_by_key = {_key_token(row[key_column]): row for row in right_rows}
    added_keys = sorted(set(right_by_key) - set(left_by_key))
    removed_keys = sorted(set(left_by_key) - set(right_by_key))
    shared_keys = sorted(set(left_by_key) & set(right_by_key))
    changes = [
        _change(left_by_key[key], right_by_key[key], schema, key_column) for key in shared_keys
    ]
    changed = [change for change in changes if change is not None]
    return {
        "key_column": key_column,
        "schema": schema,
        "left": _provenance(left_snapshot, left_rows),
        "right": _provenance(right_snapshot, right_rows),
        "added_count": len(added_keys),
        "removed_count": len(removed_keys),
        "changed_count": len(changed),
        "unchanged_count": len(shared_keys) - len(changed),
        "added": [{key_column: right_by_key[key][key_column]} for key in added_keys[:MAX_EXAMPLES]],
        "removed": [
            {key_column: left_by_key[key][key_column]} for key in removed_keys[:MAX_EXAMPLES]
        ],
        "changed": changed[:MAX_EXAMPLES],
        "examples_truncated": any(
            len(items) > MAX_EXAMPLES for items in (added_keys, removed_keys, changed)
        ),
        "live_at_call": True,
    }


def _snapshot(value: object, side: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) - {"rows", "digest"} or "rows" not in value:
        raise ValueError(f"{side} must contain rows and optional digest only")
    rows = value["rows"]
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError(f"{side}.rows must be an array with at most {MAX_ROWS} rows")
    claim = value.get("digest")
    if claim is not None and (not isinstance(claim, str) or len(claim) > 200):
        raise ValueError(f"{side}.digest must be a short string when supplied")
    return {"rows": rows, "digest": claim}


def _validate_input_size(left: Mapping[str, object], right: Mapping[str, object]) -> None:
    try:
        encoded = json.dumps(
            [left, right], ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as error:
        raise ValueError("snapshots must contain JSON-compatible scalar values") from error
    if len(encoded.encode()) > MAX_INPUT_BYTES:
        raise ValueError(f"serialized snapshots exceed {MAX_INPUT_BYTES} bytes")


def _schema(left_rows: object, right_rows: object) -> list[str]:
    left_schema = _rows_schema(left_rows, "left")
    right_schema = _rows_schema(right_rows, "right")
    if not left_schema and not right_schema:
        raise ValueError("at least one snapshot must contain a row to establish schema")
    if left_schema and right_schema and left_schema != right_schema:
        raise ValueError("left and right snapshots must have identical schemas")
    return left_schema or right_schema


def _rows_schema(rows: object, side: str) -> list[str]:
    if not isinstance(rows, list):
        raise ValueError(f"{side}.rows must be an array")
    schema: list[str] | None = None
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{side}.rows entries must be objects")
        columns = sorted(row)
        if (
            not columns
            or len(columns) > MAX_COLUMNS
            or any(
                not isinstance(column, str) or not column or len(column) > 128 for column in columns
            )
        ):
            raise ValueError(f"{side}.rows contains invalid columns")
        if schema is None:
            schema = columns
        elif columns != schema:
            raise ValueError(f"{side}.rows must use one consistent schema")
        for value in row.values():
            _validate_scalar(value, side)
    return schema or []


def _validate_scalar(value: object, side: str) -> None:
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, str) and len(value) <= MAX_STRING_CHARS:
        return
    raise ValueError(f"{side}.rows contains a non-scalar or oversized value")


def _validate_key_column(key_column: str, schema: list[str]) -> None:
    if not isinstance(key_column, str) or key_column not in schema:
        raise ValueError("key_column must be a column in both snapshot schemas")


def _canonical_rows(rows: object, schema: list[str], key_column: str) -> list[dict[str, object]]:
    assert isinstance(rows, list)
    canonical = [{column: row[column] for column in schema} for row in rows]
    keys = [row[key_column] for row in canonical]
    if any(key is None for key in keys) or len({_key_token(key) for key in keys}) != len(keys):
        raise ValueError("key_column values must be present and unique within each snapshot")
    return sorted(canonical, key=lambda row: _key_token(row[key_column]))


def _key_token(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _provenance(snapshot: Mapping[str, object], rows: list[dict[str, object]]) -> dict[str, object]:
    normalized = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    result: dict[str, object] = {
        "row_count": len(rows),
        "snapshot_digest": f"sha256:{hashlib.sha256(normalized.encode()).hexdigest()}",
    }
    if snapshot["digest"] is not None:
        result["caller_digest_claim"] = snapshot["digest"]
    return result


def _change(
    before: Mapping[str, object],
    after: Mapping[str, object],
    schema: list[str],
    key_column: str,
) -> dict[str, object] | None:
    changed_columns = {
        column: {"before": before[column], "after": after[column]}
        for column in schema
        if column != key_column and before[column] != after[column]
    }
    return (
        {key_column: before[key_column], "changed_columns": changed_columns}
        if changed_columns
        else None
    )
