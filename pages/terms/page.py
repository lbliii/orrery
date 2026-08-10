from chirp import Page


def get() -> Page:
    return Page(
        "terms/page.html", "content", page_block_name="content", page_title="Terms — Orrery"
    )
