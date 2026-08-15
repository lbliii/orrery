"""Host Rosettes helpers — highlighted samples with Orrery-owned classes.

Rosettes is a host library, not a public primitive. ``highlight()`` may emit
``<div class="rosettes">``; we rewrite that wrapper to ``class="sample"``.
Semantic spans only (``css_class_style="semantic"``).
"""

from __future__ import annotations

import json

from rosettes import highlight

_ROSETTES_WRAPPER = 'class="rosettes"'
_SAMPLE_WRAPPER = 'class="sample"'


def highlight_code(code: str, lang: str) -> str:
    """Highlight source and return a ``.sample`` HTML fragment."""
    html = highlight(code, lang, css_class="sample", css_class_style="semantic")
    return _public_sample(html)


def highlight_json(obj_or_str: object) -> str:
    """Pretty-print JSON (object or string) and highlight as a sample."""
    return highlight_code(_json_text(obj_or_str), "json")


def _json_text(obj_or_str: object) -> str:
    if isinstance(obj_or_str, str):
        try:
            obj_or_str = json.loads(obj_or_str)
        except json.JSONDecodeError:
            return obj_or_str
    return json.dumps(obj_or_str, indent=2, sort_keys=False)


def _public_sample(html: str) -> str:
    """Rewrite any public ``.rosettes`` wrapper to Orrery ``.sample``."""
    if _ROSETTES_WRAPPER in html:
        html = html.replace(_ROSETTES_WRAPPER, _SAMPLE_WRAPPER)
    return html
