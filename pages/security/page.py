from chirp import Page

from discovery import TRUST_FACTS


def get() -> Page:
    return Page(
        "security/page.html",
        "content",
        page_block_name="content",
        page_title="Security — Orrery",
        facts=TRUST_FACTS,
    )
