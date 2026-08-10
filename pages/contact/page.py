from chirp import Page

from discovery import SECURITY_CONTACT, SUPPORT_CONTACT


def get() -> Page:
    return Page(
        "contact/page.html",
        "content",
        page_block_name="content",
        page_title="Contact — Orrery",
        support_contact=SUPPORT_CONTACT,
        security_contact=SECURITY_CONTACT,
    )
