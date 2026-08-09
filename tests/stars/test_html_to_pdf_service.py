"""Artifact-level tests for the html-to-pdf Star."""

from __future__ import annotations

import base64
import hashlib

from stars.html_to_pdf import convert, health


def test_convert_returns_a_verifiable_pdf_artifact() -> None:
    result = convert("<h1>Release evidence</h1><p>Ready for review.</p>")
    pdf = base64.b64decode(result["artifact_base64"])

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert result["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert result["byte_length"] == len(pdf)
    assert result["page_count"] == 1
    assert result["content_type"] == "application/pdf"


def test_convert_extracts_visible_text_without_including_html_or_scripts() -> None:
    result = convert(
        "<style>body { color: red; }</style><h1>Hello</h1><script>secret()</script><p>World</p>"
    )
    pdf = base64.b64decode(result["artifact_base64"])

    assert b"Hello" in pdf
    assert b"World" in pdf
    assert b"<h1>" not in pdf
    assert b"secret()" not in pdf


def test_health_remains_ready() -> None:
    assert health() == {"status": "ok", "skill": "html-to-pdf"}
