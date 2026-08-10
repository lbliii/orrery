from chirp import Page


def get() -> Page:
    return Page(
        "contact/page.html", "content", page_block_name="content", page_title="Contact — Orrery"
    )
