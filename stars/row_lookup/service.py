"""Bounded exact-key lookup over a single canonical public CSV source."""

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

from .contract import DATASET_URLS, DEFAULT_DATASET, KEY_SCHEMA, MAX_BYTES, MAX_ROWS_SCANNED

TIMEOUT_SECONDS = 8
RAW_GITHUB_HOST = "raw.githubusercontent.com"
EXPECTED_HEADER = ["origin", "destination", "count"]
IATA = re.compile(r"^[A-Z]{3}$")


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
    request = urllib.request.Request(url, headers={"User-Agent": "orrery-row-lookup/0.1"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        return (
            response.geturl(),
            int(response.status),
            dict(response.headers.items()),
            response.read(max_bytes + 1),
        )


def lookup(
    dataset: str = DEFAULT_DATASET,
    key: object = None,
    *,
    fetch: Fetch = _network_fetch,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Return the unique exact-key row, without retaining source or query state."""
    validated_key = _key(key)
    if dataset not in DATASET_URLS:
        return {"error": "dataset_not_allowed", "dataset": dataset, "live_at_call": True}
    if validated_key is None:
        return {"error": "invalid_key", "dataset": dataset, "live_at_call": True}
    source_url = DATASET_URLS[dataset]
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
        row, rows_scanned = _find_row(body, validated_key)
    except UnicodeDecodeError, csv.Error, ValueError:
        return {"error": "source_malformed", "dataset": dataset, "live_at_call": True}
    if rows_scanned > MAX_ROWS_SCANNED:
        return {"error": "scan_limit_exceeded", "dataset": dataset, "live_at_call": True}

    evidence = {
        "dataset": dataset,
        "key": validated_key,
        "key_schema": KEY_SCHEMA,
        "canonical_url": source_url,
        "source_url": source_url,
        "status": status,
        "source_digest": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "schema": {"origin": "string", "destination": "string", "count": "integer"},
        "rows_scanned": rows_scanned,
        "observed_at": (clock or (lambda: datetime.now(UTC)))().isoformat(),
        "source": {"publisher": "Vega Datasets", "format": "text/csv"},
        "live_at_call": True,
    }
    if row is None:
        return {"error": "row_not_found", **evidence}
    return {"row": row, **evidence}


def _key(value: object) -> dict[str, str] | None:
    if not isinstance(value, Mapping) or set(value) != {"origin", "destination"}:
        return None
    origin, destination = value["origin"], value["destination"]
    if not isinstance(origin, str) or not isinstance(destination, str):
        return None
    if not IATA.fullmatch(origin) or not IATA.fullmatch(destination):
        return None
    return {"origin": origin, "destination": destination}


def _find_row(body: bytes, key: Mapping[str, str]) -> tuple[dict[str, object] | None, int]:
    reader = csv.reader(io.StringIO(body.decode("utf-8"), newline=""), strict=True)
    if next(reader, None) != EXPECTED_HEADER:
        raise ValueError("unexpected flights-airport CSV schema")
    found: dict[str, object] | None = None
    scanned = 0
    for values in reader:
        if not values:
            continue
        scanned += 1
        if scanned > MAX_ROWS_SCANNED:
            return None, scanned
        if len(values) != len(EXPECTED_HEADER) or not values[2].isdigit():
            raise ValueError("invalid flights-airport row")
        row = {"origin": values[0], "destination": values[1], "count": int(values[2])}
        if row["origin"] == key["origin"] and row["destination"] == key["destination"]:
            if found is not None:
                raise ValueError("duplicate source key")
            found = row
    return found, scanned
