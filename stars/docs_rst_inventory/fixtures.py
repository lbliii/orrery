"""Synthetic RST/Sphinx trees for docs/rst-inventory acceptance (#173)."""

from __future__ import annotations

from typing import Final

BASELINE_TREE: Final = [
    {
        "path": "index.rst",
        "content": (
            "Welcome\n"
            "=======\n\n"
            "See :ref:`intro` and :math:`x^2`.\n\n"
            ".. note::\n"
            "   Pinned note.\n\n"
            ".. include:: partial.rst\n\n"
            ".. image:: ./assets/logo.png\n"
            "   :alt: Logo\n\n"
            ".. |version| replace:: 1.0\n\n"
            "Release |version|.\n"
        ),
    },
    {
        "path": "partial.rst",
        "content": (
            "Partial\n"
            "-------\n\n"
            ".. toctree::\n"
            "   :maxdepth: 1\n\n"
            "   guide\n\n"
            ".. list-table:: Sample\n"
            "   :header-rows: 1\n\n"
            "   * - A\n"
            "     - B\n"
            "   * - 1\n"
            "     - 2\n"
        ),
    },
    {
        "path": "guide.rst",
        "content": (
            "Guide\n"
            "~~~~~\n\n"
            ".. code-block:: python\n\n"
            "   print('ok')\n\n"
            ".. automodule:: pkg.module\n"
            "   :members:\n\n"
            ".. raw:: html\n\n"
            "   <div class=\"custom\"></div>\n\n"
            ".. custom-macro::\n"
            "   Unsupported extension directive.\n\n"
            "Call :func:`pkg.module.fn`.\n"
        ),
    },
]

MALFORMED_TREE: Final = [
    {
        "path": "broken.rst",
        "content": (
            "Broken\n"
            "======\n\n"
            "..\n"
            " orphan ellipsis\n"
        ),
    },
]

SAFE_ONLY_TREE: Final = [
    {
        "path": "safe.rst",
        "content": (
            "Safe page\n"
            "=========\n\n"
            ".. code-block:: text\n\n"
            "   hello\n\n"
            ".. image:: ./ok.png\n"
        ),
    },
]
