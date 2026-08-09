"""Product chrome helpers — console deep-links for resolve/star surfaces."""

from __future__ import annotations

from .models import ResolveRecord

#: Resolve catalog name → mounted dogfood skill for ``/console/{skill}``.
RECORD_CONSOLE_SKILL: dict[str, str] = {
    "orrery/html-to-pdf": "html-to-pdf",
    "orrery/world-time": "world-time",
    "orrery/source-watch": "source-watch",
    "gaze": "gaze",
    "resolve": "resolve",
}


def console_href_for(record: ResolveRecord) -> str:
    """Reliability console URL aligned with publish-oracle scores."""
    skill = RECORD_CONSOLE_SKILL.get(record.name)
    if skill:
        return f"/console/{skill}"
    if record.kind == "star" and record.namespace:
        return f"/console/{record.short_name}"
    return "/console"


PUBLISHER_DIRECT_NOTE = (
    "Agents call the resolved MCP endpoint directly. Orrery is Skill DNS + "
    "trust surfaces — not a reverse proxy for tool execution."
)
