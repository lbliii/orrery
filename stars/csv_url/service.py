"""Bounded canonical CSV retrieval for a fixed public dataset allowlist."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contract import DATASET_URLS, DEFAULT_DATASET, MAX_BYTES, MAX_ROWS

TIMEOUT_SECONDS = 8
RAW_GITHUB_HOST = "raw.githubusercontent.com"
_INTEGER = re.compile(r"[+-]?\d+")


class Fetch(Protocol):
    def __call__(
        self, url: str, *, timeout: float, max_bytes: int
    ) -> tuple[str, int, Mapping[str, str], bytes]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _network_fetch(
    url: str, *, timeout: float, max_bytes: int
) -> tuple[str, int, Mapping[str, str], bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "orrery-csv-url/0.1"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        return (
            response.geturl(),
            int(response.status),
            dict(response.headers.items()),
            response.read(max_bytes + 1),
        )


def get(
    dataset: str = DEFAULT_DATASET,
    *,
    fetch: Fetch = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Read a named dataset without accepting a caller-supplied URL."""
    observed = (clock or (lambda: datetime.now(UTC)))().isoformat()
    source_url = DATASET_URLS.get(dataset)
    if source_url is None:
        return {"error": "dataset_not_allowed", "dataset": dataset, "live_at_call": True}
    try:
        final_url, status, _headers, body = fetch(
            source_url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES
        )
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as error:
        return {
            "error": "upstream_unreachable",
            "dataset": dataset,
            "detail": str(error),
            "live_at_call": True,
        }

    final = urlsplit(final_url)
    if final.scheme != "https" or final.hostname != RAW_GITHUB_HOST or final_url != source_url:
        return {"error": "redirect_not_allowed", "dataset": dataset, "live_at_call": True}
    if len(body) > MAX_BYTES:
        return {"error": "upstream_too_large", "dataset": dataset, "live_at_call": True}
    try:
        header, raw_rows = _parse_csv(body)
    except UnicodeDecodeError, csv.Error, ValueError:
        return {"error": "source_malformed", "dataset": dataset, "live_at_call": True}

    schema = _infer_schema(header, raw_rows)
    rows = [_typed_row(header, row, schema) for row in raw_rows[:MAX_ROWS]]
    return {
        "dataset": dataset,
        "source_url": source_url,
        "canonical_url": source_url,
        "status": status,
        "source_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "schema": schema,
        "row_count": len(raw_rows),
        "rows": rows,
        "rows_truncated": len(raw_rows) > MAX_ROWS,
        "max_rows": MAX_ROWS,
        "observed_at": observed,
        "source": {"publisher": "Vega Datasets", "format": "text/csv"},
        "live_at_call": True,
    }


def _parse_csv(body: bytes) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(body.decode("utf-8"), newline=""), strict=True)
    header = next(reader, None)
    if (
        not header
        or any(not name or not name.strip() for name in header)
        or len(set(header)) != len(header)
    ):
        raise ValueError("CSV header is missing, blank, or duplicated")
    rows: list[list[str]] = []
    for row in reader:
        if not row:
            continue
        if len(row) != len(header):
            raise ValueError("CSV row width does not match header")
        rows.append(row)
    return header, rows


def _infer_schema(header: list[str], rows: list[list[str]]) -> dict[str, str]:
    return {name: _infer_type([row[index] for row in rows]) for index, name in enumerate(header)}


def _infer_type(values: list[str]) -> str:
    nonempty = [value for value in values if value != ""]
    if not nonempty:
        return "string"
    lowered = [value.lower() for value in nonempty]
    if all(value in {"true", "false"} for value in lowered):
        return "boolean"
    if all(_INTEGER.fullmatch(value) for value in nonempty):
        return "integer"
    try:
        for value in nonempty:
            float(value)
    except ValueError:
        return "string"
    return "number"


def _typed_row(header: list[str], row: list[str], schema: Mapping[str, str]) -> dict[str, object]:
    return {name: _coerce(value, schema[name]) for name, value in zip(header, row, strict=True)}


def _coerce(value: str, value_type: str) -> object:
    if value == "":
        return None
    if value_type == "boolean":
        return value.lower() == "true"
    if value_type == "integer":
        return int(value)
    if value_type == "number":
        return float(value)
    return value
