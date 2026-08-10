"""Synthetic MyST trees for docs/myst-to-mdx-safe acceptance (#170)."""

from __future__ import annotations

from typing import Final

# Corpus-backed safe subset: heading + transformable admonition only.
SAFE_TREE: Final = [
    {
        "path": "index.md",
        "content": (
            "# Welcome\n\n"
            "Plain paragraph.\n\n"
            "```{note}\n"
            "Pinned note.\n"
            "```\n"
        ),
    },
    {
        "path": "guide.md",
        "content": ("## Guide\n\n" "Body text only.\n"),
    },
]

# Every unsupported / decision_required fixture must surface as findings.
UNSUPPORTED_TREE: Final = [
    {
        "path": "includes.md",
        "content": (
            "# Includes\n\n"
            "```{include} partial.md\n"
            "```\n"
        ),
    },
    {
        "path": "custom.md",
        "content": (
            "### Custom\n\n"
            "::: {custom-macro}\n"
            "Unsupported colon fence.\n"
            ":::\n"
        ),
    },
    {
        "path": "roles.md",
        "content": ("See {ref}`intro` and {math}`x^2`.\n"),
    },
]

MALFORMED_TREE: Final = [
    {
        "path": "broken.md",
        "content": ("# Broken\n\n" "```{note}\n" "Missing closing fence.\n"),
    },
]
