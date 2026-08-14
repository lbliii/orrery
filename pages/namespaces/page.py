"""Namespaces — the private "company Skill DNS" pitch (SaaS wedge).

Create is an HTML form: JS-off POST+303 and an htmx fragment (#476).
JSON ``POST /api/namespaces`` stays for machines. Backs GitHub epic #6.
"""

from __future__ import annotations

from urllib.parse import quote

from chirp import Fragment, MutationResult, Page, Redirect, Request, ValidationError

from catalog import CATALOG
from namespaces import ProvisionError, provision_namespace
from pages.namespaces._errors import PageErrorCopy, describe

_CREATE = "/namespaces"


def _panel(
    *,
    slug: str = "",
    created_id: str = "",
    error: PageErrorCopy | None = None,
) -> dict[str, object]:
    return {"slug": slug, "created_id": created_id, "error": error}


def _page(**panel: object) -> Page:
    return Page(
        "namespaces/page.html",
        "create_panel",
        page_block_name="content",
        page_title="Private namespaces — Orrery",
        footer_note="Private namespaces",
        footer_meta="public free · namespace paid",
        **panel,
    )


def _error_redirect(code: str, slug: str) -> Redirect:
    query = f"error={quote(code, safe='')}"
    if slug:
        query += f"&id={quote(slug, safe='')}"
    return Redirect(f"{_CREATE}?{query}", status=303)


def get(request: Request) -> Page:
    created_id = (request.query.get("created") or "").strip()
    raw_error = (request.query.get("error") or "").strip()
    slug = (request.query.get("id") or "").strip()
    error = describe(raw_error) if raw_error else None
    if created_id:
        error = None
        slug = ""
    return _page(**_panel(slug=slug, created_id=created_id, error=error))


async def post(request: Request) -> MutationResult | ValidationError | Redirect:
    form = await request.form()
    raw_id = form.get("id")
    slug = raw_id.strip() if isinstance(raw_id, str) else ""
    try:
        result = provision_namespace(slug, catalog=CATALOG)
    except ProvisionError as exc:
        error = describe(exc.code)
        if request.is_htmx:
            return ValidationError(
                "namespaces/page.html",
                "create_panel",
                **_panel(slug=slug, error=error),
            )
        return _error_redirect(error.code or exc.code, slug)
    created = str(result["id"])
    return MutationResult(
        f"{_CREATE}?created={quote(created, safe='')}",
        Fragment(
            "namespaces/page.html",
            "create_panel",
            **_panel(created_id=created),
        ),
    )
