"""Re-export migration star fixtures for constellation acceptance (#178)."""

from __future__ import annotations

from stars.docs_myst_to_mdx_safe.fixtures import (
    MALFORMED_TREE,
    SAFE_TREE,
    UNSUPPORTED_TREE,
)

__all__ = ["MALFORMED_TREE", "SAFE_TREE", "UNSUPPORTED_TREE"]
