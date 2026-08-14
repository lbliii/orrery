"""Framework-free Source Watch domain service.

Only one source is admitted in v1.  Fetches are bounded, redirects are denied,
and the process-local history exists solely to compare observations in one
running service instance.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from urllib.parse import urlsplit

from stars._core.http_egress import open_https

from .contract import ANSWER_MAX_CHARS, DEFAULT_SOURCE

SOURCES: dict[str, str] = {
    DEFAULT_SOURCE: "https://docs.python.org/3/whatsnew/3.14.html",
}
ALLOWED_HOSTS = frozenset({"docs.python.org"})
TIMEOUT_SECONDS = 8
MAX_BYTES = 1 * 1024 * 1024

# V1 history is intentionally process-local and non-durable.
_history: dict[str, list[dict[str, object]]] = {}


def _error(error: str, *, source: str, detail: str = "") -> dict[str, object]:
    payload: dict[str, object] = {"error": error, "source": source, "live_at_call": True}
    if detail:
        payload["detail"] = detail
    return payload


def _fixture(source: str) -> str | None:
    raw = os.environ.get("ORRERY_SOURCE_WATCH_FIXTURES", "").strip()
    if not raw:
        return None
    fixtures = json.loads(raw)
    if not isinstance(fixtures, dict):
        raise ValueError("ORRERY_SOURCE_WATCH_FIXTURES must be a JSON object")
    if source not in fixtures:
        return None
    value = fixtures[source]
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("body", "document", "text"):
            document = value.get(key)
            if isinstance(document, str):
                return document
    raise ValueError(f"fixture for {source!r} must be a string or document object")


def _normalise(document: str) -> str:
    return "\n".join(line.rstrip() for line in document.replace("\r\n", "\n").split("\r"))


def _sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _fetch(source: str) -> dict[str, object]:
    url = SOURCES.get(source)
    if url is None:
        return _error("source_not_allowed", source=source)
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        return _error("source_not_allowed", source=source)
    try:
        fixture = _fixture(source)
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        return _error("fixture_invalid", source=source, detail=str(exc))
    if fixture is not None:
        return {"document": fixture, "canonical_url": url, "fixture": True}

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "orrery-source-watch/0.1 (+https://github.com/lbliii/orrery)",
            "Accept": "text/plain,text/html;q=0.9,*/*;q=0.1",
        },
    )
    try:
        with open_https(request, timeout=TIMEOUT_SECONDS) as response:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
                return _error("redirect_not_allowed", source=source)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_BYTES:
                return _error("upstream_too_large", source=source)
            body = response.read(MAX_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        return _error("upstream_unreachable", source=source, detail=str(exc))
    except ValueError as exc:
        return _error("upstream_malformed", source=source, detail=str(exc))
    if len(body) > MAX_BYTES:
        return _error("upstream_too_large", source=source)
    return {
        "document": body.decode("utf-8", errors="replace"),
        "canonical_url": url,
        "fixture": False,
    }


def observe(source: str = DEFAULT_SOURCE) -> dict[str, object]:
    """Capture a source and record raw and normalized content digests."""
    fetched = _fetch(source)
    if "error" in fetched:
        return fetched
    document = str(fetched["document"])
    normalised = _normalise(document)
    history = _history.setdefault(source, [])
    digest = _sha256(normalised)
    state = (
        "new"
        if not history
        else "unchanged"
        if history[-1]["normalized_sha256"] == digest
        else "changed"
    )
    observation: dict[str, object] = {
        "source": source,
        "canonical_url": fetched["canonical_url"],
        "retrieved_at": datetime.now(UTC).isoformat(),
        "raw_sha256": _sha256(document),
        "normalized_sha256": digest,
        "status": state,
        "live_at_call": True,
        "document": document,
        "fixture": fetched["fixture"],
    }
    history.append(observation)
    return {key: value for key, value in observation.items() if key != "document"}


def diff(source: str = DEFAULT_SOURCE, since_digest: str = "") -> dict[str, object]:
    """Fetch now, then summarize whether it differs from a known digest."""
    history = _history.get(source, [])
    prior_digest = str(history[-1]["normalized_sha256"]) if history else ""
    observed = observe(source)
    if "error" in observed:
        return observed
    latest = _history[source][-1]
    current = str(latest["normalized_sha256"])
    known = since_digest.strip() or prior_digest
    evidence = {
        "canonical_url": latest["canonical_url"],
        "retrieved_at": latest["retrieved_at"],
        "raw_sha256": latest["raw_sha256"],
        "normalized_sha256": current,
    }
    if not known:
        return {
            "source": source,
            "status": "new",
            "current_digest": current,
            "evidence": evidence,
            "live_at_call": True,
            "summary": "No prior digest is available; this is the first observation.",
        }
    status = "unchanged" if known == current else "changed"
    return {
        "source": source,
        "status": status,
        "known_digest": known,
        "current_digest": current,
        "evidence": evidence,
        "live_at_call": True,
        "summary": "The normalized source is unchanged from the known digest."
        if status == "unchanged"
        else "The normalized source differs from the known digest.",
    }


def _excerpt(document: str, question: str, *, limit: int) -> str:
    compact = " ".join(document.split())
    terms = [term.lower() for term in question.split() if len(term) > 2]
    lowered = compact.lower()
    index = next((lowered.find(term) for term in terms if lowered.find(term) >= 0), 0)
    start = max(0, compact.rfind(" ", 0, index - 120)) if index > 0 else 0
    excerpt = compact[start : start + limit]
    return excerpt + ("…" if start + limit < len(compact) else "")


def answer(
    question: str, source: str = DEFAULT_SOURCE, max_chars: int = ANSWER_MAX_CHARS
) -> dict[str, object]:
    """Fetch now, then return a bounded extractive answer with evidence."""
    if max_chars < 1 or max_chars > ANSWER_MAX_CHARS:
        return _error("invalid_answer_limit", source=source)
    result = observe(source)
    if "error" in result:
        return result
    latest = _history[source][-1]
    return {
        "source": source,
        "answer": _excerpt(str(latest["document"]), question, limit=max_chars),
        "extractive": True,
        "source_digest": latest["normalized_sha256"],
        "live_at_call": True,
        "evidence": {
            "canonical_url": latest["canonical_url"],
            "retrieved_at": latest["retrieved_at"],
            "normalized_sha256": latest["normalized_sha256"],
        },
    }
