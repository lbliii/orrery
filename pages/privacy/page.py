from chirp import Page


def get() -> Page:
    return Page(
        "privacy/page.html", "content", page_block_name="content", page_title="Privacy — Orrery"
    )
