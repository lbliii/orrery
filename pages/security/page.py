from chirp import Page

from discovery import GITHUB_REPO, SECURITY_CONTACT, TRUST_FACTS


def get() -> Page:
    return Page(
        "security/page.html",
        "content",
        page_block_name="content",
        page_title="Security — Orrery",
        facts=TRUST_FACTS,
        repository=GITHUB_REPO,
        security_contact=SECURITY_CONTACT,
    )
