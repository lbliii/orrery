from chirp import Page

from discovery import TRUST_FACTS


def get() -> Page:
    return Page(
        "privacy/page.html",
        "content",
        page_block_name="content",
        page_title="Privacy — Orrery",
        facts=TRUST_FACTS,
    )
