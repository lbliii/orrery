"""Root page context — brand chrome shared by every screen.

Provides ``current_path`` and a ``nav`` map so ``_layout.html`` can mark the
active primary-nav link (mirrors ``aria-current="page"`` in the mocks).
"""

from __future__ import annotations

from chirp import Request


def context(request: Request) -> dict:
    path = request.path
    return {
        "current_path": path,
        "nav": {
            "home": path == "/",
            "gaze": path.startswith("/gaze"),
            "resolve": path.startswith("/resolve"),
            "stars": path.startswith("/stars"),
            "constellations": path.startswith("/constellations"),
            "namespaces": path.startswith("/namespaces"),
            "console": path.startswith("/console"),
        },
    }
