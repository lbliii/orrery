"""Root page context — brand chrome shared by every screen.

Provides ``current_path`` and a ``nav`` map so ``_layout.html`` can mark the
active primary-nav link (mirrors ``aria-current="page"`` in the mocks).

``nav.product`` is true on any Product child route (including ``/star/*``).
"""

from __future__ import annotations

from chirp import Request


def context(request: Request) -> dict:
    path = request.path
    nav = {
        "home": path == "/",
        "gaze": path.startswith("/gaze"),
        "resolve": path.startswith("/resolve"),
        "stars": path.startswith("/stars"),
        "constellations": path.startswith("/constellations"),
        "namespaces": path.startswith("/namespaces"),
        "connect": path.startswith("/connect"),
        "product_overview": path == "/product",
        "how_it_works": path == "/how-it-works",
        "receipts": path == "/receipts",
        "for_harnesses": path == "/for-harnesses",
        "pricing": path == "/pricing",
        "star": path.startswith("/star/"),
    }
    nav["product"] = (
        nav["product_overview"]
        or nav["how_it_works"]
        or nav["gaze"]
        or nav["resolve"]
        or nav["stars"]
        or nav["constellations"]
        or nav["receipts"]
        or nav["namespaces"]
        or nav["for_harnesses"]
        or nav["pricing"]
        or nav["star"]
    )
    return {
        "current_path": path,
        "nav": nav,
    }
