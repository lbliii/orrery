"""Closed managed-CPU job handlers for the initial artifact specimen Stars."""

from __future__ import annotations

import base64
import csv
import io
import struct
import zlib
from collections.abc import Mapping
from typing import Any

from runs import RunRecord
from runs.worker import JobHandlerRegistry
from stars.html_to_pdf.artifacts import DurablePdfArtifactService, get_pdf_artifacts
from stars.html_to_pdf.service import convert as render_pdf

_POLICIES = {
    "html-to-pdf": {"cpu_millicores": 250, "wall_time_seconds": 30, "max_output_bytes": 1048576},
    "csv-report": {"cpu_millicores": 250, "wall_time_seconds": 30, "max_output_bytes": 1048576},
    "image-transform": {
        "cpu_millicores": 250,
        "wall_time_seconds": 30,
        "max_output_bytes": 1048576,
    },
}


def build_registry(artifacts: DurablePdfArtifactService | None = None) -> JobHandlerRegistry:
    """Return the exact handler allowlist installed in the separate worker."""
    service = artifacts or get_pdf_artifacts()
    registry = JobHandlerRegistry()
    registry.register("html-to-pdf", lambda record: _pdf(record, service))
    registry.register("csv-report", lambda record: _csv(record, service))
    registry.register("image-transform", lambda record: _image(record, service))
    return registry


def _pdf(record: RunRecord, service: Any) -> dict[str, object]:
    html = _input(record, "html")
    if not isinstance(html, str):
        raise ValueError("html-to-pdf requires string html")
    data = base64.b64decode(str(render_pdf(html)["artifact_base64"]), validate=True)
    return _publish(record, service, data, "application/pdf", "document.pdf")


def _csv(record: RunRecord, service: Any) -> dict[str, object]:
    rows = _input(record, "rows")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("csv-report requires rows as a list of objects")
    fields = sorted({str(key) for row in rows for key in row})
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return _publish(record, service, stream.getvalue().encode(), "text/csv", "report.csv")


def _image(record: RunRecord, service: Any) -> dict[str, object]:
    color = _input(record, "color")
    if not isinstance(color, str):
        raise ValueError("image-transform requires a hex color")
    raw = color.removeprefix("#")
    if len(raw) != 6 or any(char not in "0123456789abcdefABCDEF" for char in raw):
        raise ValueError("color must be a six-digit hex RGB value")
    pixel = bytes(255 - value for value in bytes.fromhex(raw)) + b"\xff"
    data = _png(pixel)
    return _publish(record, service, data, "image/png", "inverted.png")


def _input(record: RunRecord, key: str) -> object:
    descriptor = record.job or {}
    payload = descriptor.get("input")
    return payload.get(key) if isinstance(payload, Mapping) else None


def _publish(
    record: RunRecord, service: Any, data: bytes, content_type: str, filename: str
) -> dict[str, object]:
    policy = _POLICIES[str((record.job or {}).get("kind"))]
    if len(data) > policy["max_output_bytes"]:
        raise ValueError("workload output exceeded pinned policy")
    artifact = service.publish(data, content_type=content_type, filename=filename)
    return {
        "run_id": record.run_id,
        "executor": "managed-cpu-worker",
        "workload": str((record.job or {}).get("kind")),
        "policy": policy,
        "artifact_id": artifact.artifact_id,
        "artifact_url": f"/artifacts/{artifact.artifact_id}",
        "sha256": artifact.sha256,
        "content_type": content_type,
        "filename": filename,
        "byte_length": len(data),
    }


def _png(pixel: bytes) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0" + pixel))
        + chunk(b"IEND", b"")
    )
