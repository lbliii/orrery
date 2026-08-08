"""Resolve — the "Skill DNS" console + agent JSON contract.

HTML console lists the public zone and supports ``?q=`` lookup (mock parity).
Agents use the mock contract ``GET /resolve?name=…`` (or ``Accept: application/json``)
and receive the same record as ``/api/resolve`` / MCP ``resolve_name``.

Backs GitHub epic #5 (Resolve) / issue #20.
"""

from __future__ import annotations

from chirp import JSONResponse, Page, Request

from catalog import CATALOG


def _wants_json(request: Request) -> bool:
    """True when the client asked for the JSON DNS contract."""
    if (request.query.get("name") or "").strip():
        return True
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" not in accept:
        return False
    # Prefer HTML when the browser lists it first (typical navigation).
    first = accept.split(",", 1)[0].strip()
    return not first.startswith("text/html")


def get(request: Request) -> Page | JSONResponse:
    if _wants_json(request):
        name = (request.query.get("name") or request.query.get("q") or "").strip()
        record = CATALOG.resolve(name) if name else None
        if record is None:
            return JSONResponse.from_value(
                {"error": "not_found", "name": name}, status=404
            )
        return JSONResponse.from_value(record.as_dict())

    q = (request.query.get("q") or "").strip()
    matched = CATALOG.resolve(q) if q else None
    return Page(
        "resolve/page.html",
        "content",
        page_block_name="content",
        page_title="Resolve — Orrery",
        footer_note="Resolver console",
        records=CATALOG.public_records(),
        q=q,
        matched=matched,
        matched_name=matched.name if matched else "",
    )
