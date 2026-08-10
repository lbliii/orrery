from chirp import Page

from discovery import TRUST_FACTS, configured_public_origin


def get() -> Page:
    return Page(
        "trust/allowlist/page.html",
        "content",
        page_block_name="content",
        page_title="Trust allowlist — Orrery",
        facts=TRUST_FACTS,
        public_origin=configured_public_origin() or "https://orrery.lol",
    )
