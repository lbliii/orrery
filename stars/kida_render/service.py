"""Pure Kida HTML render over caller-supplied template bytes and JSON data."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from kida import Environment

from .contract import (
    ALLOWED_SUFFIXES,
    ALLOWED_SURFACES,
    MAX_DATA_JSON_BYTES,
    MAX_OUTPUT_BYTES,
    MAX_PATH_LEN,
    MAX_TEMPLATE_BYTES,
    WALL_TIMEOUT_SECONDS,
)

_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")

_OUTPUT_TOO_LARGE_REMEDIATION = (
    "Rendered HTML exceeds the sync output cap. Retry with a smaller template or "
    "data payload, or use a future async artifact path when available."
)

_RENDER_TIMEOUT_REMEDIATION = (
    "Rendering exceeded the wall timeout. Simplify the template or retry with "
    "smaller inputs."
)


def render(
    template: object,
    data: object,
    *,
    surface: str = "html",
) -> dict[str, object]:
    """Render Kida template bytes with JSON data to a bounded HTML surface."""
    if surface not in ALLOWED_SURFACES:
        return {"error": "surface_invalid", "surface": surface}

    source, error = _parse_template(template)
    if error is not None:
        return error
    assert source is not None

    if not isinstance(data, Mapping):
        return {"error": "data_invalid"}
    data_obj = dict(data)
    data_bytes = canonical_json_bytes(data_obj)
    if len(data_bytes) > MAX_DATA_JSON_BYTES:
        return {"error": "data_too_large"}

    tmpl_digest = template_digest(source)
    data_dgst = data_digest(data_obj)

    def _do_render() -> str:
        env = Environment(max_include_depth=0)
        return env.render_string(source, data_obj)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_do_render)
            html = future.result(timeout=WALL_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        return {
            "error": "render_timeout",
            "remediation": _RENDER_TIMEOUT_REMEDIATION,
        }
    except Exception as exc:
        return {
            "error": "render_failed",
            "message": str(exc),
        }

    output_bytes = unicodedata.normalize("NFC", html).encode("utf-8")
    if len(output_bytes) > MAX_OUTPUT_BYTES:
        return {
            "error": "output_too_large",
            "output_bytes": len(output_bytes),
            "max_output_bytes": MAX_OUTPUT_BYTES,
            "remediation": _OUTPUT_TOO_LARGE_REMEDIATION,
        }

    out_digest = output_digest(html)
    return {
        "html": html,
        "surface": surface,
        "template_digest": tmpl_digest,
        "data_digest": data_dgst,
        "output_digest": out_digest,
    }


def canonical_json_bytes(value: Any) -> bytes:
    """UTF-8 JSON with sorted keys, compact separators, NFC-normalized strings."""
    return json.dumps(
        _nfc_normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def template_digest(template: str) -> str:
    """Lowercase hex sha256 over NFC-normalized UTF-8 template bytes."""
    body = unicodedata.normalize("NFC", template).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def data_digest(data: Mapping[str, Any]) -> str:
    """Lowercase hex sha256 over canonical JSON bytes for ``data``."""
    return hashlib.sha256(canonical_json_bytes(data)).hexdigest()


def output_digest(html: str) -> str:
    """Lowercase hex sha256 over NFC-normalized UTF-8 rendered HTML bytes."""
    body = unicodedata.normalize("NFC", html).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _nfc_normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {key: _nfc_normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_nfc_normalize(item) for item in value]
    return value


def _parse_template(
    template: object,
) -> tuple[str | None, dict[str, object] | None]:
    if isinstance(template, str):
        if not template:
            return None, {"error": "template_invalid"}
        if len(template.encode("utf-8")) > MAX_TEMPLATE_BYTES:
            return None, {"error": "template_too_large"}
        return template, None

    if isinstance(template, Mapping):
        return _parse_template_entry(template, index=0)

    if isinstance(template, list):
        if len(template) != 1:
            return None, {"error": "template_invalid"}
        entry = template[0]
        if not isinstance(entry, Mapping):
            return None, {"error": "template_invalid", "index": 0}
        return _parse_template_entry(entry, index=0)

    return None, {"error": "template_invalid"}


def _parse_template_entry(
    raw: Mapping[str, object],
    *,
    index: int,
) -> tuple[str | None, dict[str, object] | None]:
    if set(raw) - {"path", "content"}:
        return None, {"error": "entry_unknown_fields", "index": index}
    path = raw.get("path")
    content = raw.get("content")
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
        return None, {"error": "path_invalid", "index": index}
    if not path.endswith(ALLOWED_SUFFIXES):
        return None, {
            "error": "path_not_template",
            "path": path,
            "index": index,
        }
    if path.startswith("/") or path.startswith("../") or "/../" in f"/{path}/":
        return None, {"error": "path_traversal", "path": path, "index": index}
    if not _PATH_RE.fullmatch(path):
        return None, {"error": "path_invalid", "path": path, "index": index}
    if not isinstance(content, str) or not content:
        return None, {"error": "content_invalid", "path": path, "index": index}
    if len(content.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        return None, {"error": "content_too_large", "path": path, "index": index}
    return content, None
