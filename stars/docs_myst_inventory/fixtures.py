"""Synthetic MyST trees for docs/myst-inventory acceptance (#169)."""

from __future__ import annotations

from typing import Final

BASELINE_TREE: Final = [
    {
        "path": "index.md",
        "content": (
            "# Welcome\n\n"
            "See {ref}`intro` and {math}`x^2`.\n\n"
            "![logo](./assets/logo.png)\n\n"
            "```{note}\n"
            "Pinned note.\n"
            "```\n\n"
            "```{include} partial.md\n"
            "```\n"
        ),
    },
    {
        "path": "partial.md",
        "content": (
            "## Partial\n\n"
            "Link to [guide](./guide.md).\n\n"
            "```{toctree}\n"
            ":maxdepth: 1\n"
            "guide\n"
            "```\n"
        ),
    },
    {
        "path": "guide.md",
        "content": (
            "### Guide\n\n"
            "```python\n"
            "print('ok')\n"
            "```\n\n"
            "::: {custom-macro}\n"
            "Unsupported colon fence.\n"
            ":::\n"
        ),
    },
]

MALFORMED_TREE: Final = [
    {
        "path": "broken.md",
        "content": (
            "# Broken\n\n"
            "```{note}\n"
            "Missing closing fence.\n"
        ),
    },
    {
        "path": "bad-colon.md",
        "content": (
            "::: {note}\n"
            "Unclosed colon fence.\n"
        ),
    },
]

