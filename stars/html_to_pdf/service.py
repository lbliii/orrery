"""Framework-free html-to-pdf service.

The Star intentionally retains the current lightweight conversion stub: the
signed Envelope plumbing is the product under test, not a PDF engine.
"""

from __future__ import annotations


def convert(html: str) -> dict[str, object]:
    """Return deterministic PDF conversion metrics for UTF-8 HTML."""
    raw = html.encode("utf-8")
    return {
        "pages": max(1, (len(raw) + 1499) // 1500),
        "bytes_hint": len(raw) + 1024,
        "content_type": "application/pdf",
    }


def health() -> dict[str, str]:
    """Report readiness for the conversion Star."""
    return {"status": "ok", "skill": "html-to-pdf"}
