"""Fixtures for docs/mdx-validate-and-migration-diff acceptance (#172)."""

from __future__ import annotations

from typing import Final

# Clean safe transform: heading + converted admonition.
SAFE_SOURCE: Final = [
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
        "content": "## Guide\n\nBody text only.\n",
    },
]

SAFE_TARGET: Final = [
    {
        "path": "index.md",
        "content": (
            "# Welcome\n\n"
            "Plain paragraph.\n\n"
            '<Admonition type="note">\n'
            "Pinned note.\n"
            "</Admonition>\n"
        ),
    },
    {
        "path": "guide.md",
        "content": "## Guide\n\nBody text only.\n",
    },
]

# Syntax build fails: unbalanced Admonition tags.
BUILD_FAIL_TARGET: Final = [
    {
        "path": "index.md",
        "content": (
            "# Welcome\n\n"
            '<Admonition type="note">\n'
            "Pinned note.\n"
            # missing close
        ),
    },
    {
        "path": "guide.md",
        "content": "## Guide\n\nBody text only.\n",
    },
]

# Syntax passes but semantic loss: heading+admonition source → heading only.
SEMANTIC_LOSS_TARGET: Final = [
    {
        "path": "index.md",
        "content": "# Welcome\n\nPlain paragraph.\n",
    },
    {
        "path": "guide.md",
        "content": "## Guide\n\nBody text only.\n",
    },
]

LINK_ASSET_REPORT_UNRESOLVED: Final = {
    "links": [
        {
            "path": "index.md",
            "kind": "link",
            "before": "./missing.md",
            "after": "./missing.md",
            "status": "unresolved",
        },
        {
            "path": "index.md",
            "kind": "asset",
            "before": "./gone.png",
            "after": "./gone.png",
            "status": "unresolved",
        },
    ],
    "frontmatter": [],
}
