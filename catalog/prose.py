"""Host Patitas helper — sanitized markdown wrapped in Orrery ``.prose``."""

from __future__ import annotations

from patitas import parse, render, sanitize
from patitas.sanitize import web_safe


def render_prose(md: str) -> str:
    """Sanitize markdown, render HTML, and wrap in ``<div class="prose">``."""
    doc = parse(md)
    html = render(sanitize(doc, policy=web_safe))
    return f'<div class="prose">{html}</div>'
