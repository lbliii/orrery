"""Host Patitas/Rosettes helpers (#502)."""

from __future__ import annotations

import json

import pytest
from rosettes import highlight

from catalog.prose import render_prose
from catalog.sample import highlight_code, highlight_json


@pytest.mark.issue(502)
def test_highlight_code_uses_sample_not_rosettes() -> None:
    html = highlight_code("def greet():\n    return 1\n", "python")
    assert 'class="sample"' in html
    assert "syntax-" in html
    assert "rosettes" not in html
    assert "def" in html


@pytest.mark.issue(502)
def test_highlight_rewrites_rosettes_wrapper() -> None:
    raw = highlight('{"ok": true}', "json", css_class_style="semantic")
    assert 'class="rosettes"' in raw
    html = highlight_json('{"ok": true}')
    assert 'class="sample"' in html
    assert "rosettes" not in html


@pytest.mark.issue(502)
def test_highlight_json_accepts_object_and_string() -> None:
    payload = {"method": "tools/call", "params": {"name": "answer"}}
    from_obj = highlight_json(payload)
    from_str = highlight_json(json.dumps(payload, indent=2))
    assert "syntax-string" in from_obj
    assert "syntax-string" in from_str
    assert 'class="sample"' in from_obj
    assert "tools/call" in from_obj
    assert "tools/call" in from_str


@pytest.mark.issue(502)
def test_highlight_json_pretty_prints_compact_string() -> None:
    html = highlight_json('{"a":1}')
    assert "syntax-number" in html
    assert "\n" in html or "  " in html


@pytest.mark.issue(502)
def test_render_prose_wraps_and_sanitizes() -> None:
    html = render_prose(
        "# Hello\n\nA [trick](javascript:alert(1)) and <script>alert(1)</script>."
    )
    assert html.startswith('<div class="prose">')
    assert html.endswith("</div>")
    assert "<h1" in html
    assert "Hello" in html
    assert "javascript:" not in html
    assert "<script" not in html
