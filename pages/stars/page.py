"""Public Star catalog — a browseable entry point into the Orrery."""

from chirp import Page, Request

from catalog import CATALOG
from stars._core.definition import CAPABILITY_FAMILY_LABELS


def get(request: Request) -> Page:
    """Render the public sky; legacy ``?name=`` stays usable as a detail view."""
    legacy_name = (request.query.get("name") or "").strip()
    if legacy_name:
        # The canonical page is mounted in app.py; this template retains a
        # usable legacy address for existing links without hiding the catalog.
        from catalog.star_page import page_for_star

        return page_for_star(legacy_name, request=request)

    stars = tuple(
        record
        for record in CATALOG.public_records()
        if record.kind == "star" and not record.index_tier
    )
    families = tuple(
        (family, CAPABILITY_FAMILY_LABELS[family])
        for family in sorted({family for star in stars for family in star.capability_families})
    )
    return Page(
        "stars/page.html",
        "content",
        page_block_name="content",
        stars=stars,
        families=families,
        family_labels=CAPABILITY_FAMILY_LABELS,
        page_title="Explore Stars — Orrery",
        footer_note="Public Star catalog",
        footer_meta="browse → understand → point",
    )
