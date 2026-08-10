from chirp import Page

from discovery import TRUST_FACTS


def get() -> Page:
    return Page(
        "terms/page.html",
        "content",
        page_block_name="content",
        page_title="Terms — Orrery",
        facts=TRUST_FACTS,
    )
