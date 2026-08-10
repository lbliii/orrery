from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="docs-rst-inventory-baseline",
        prompt=(
            "Inventory a small Sphinx RST tree with admonitions, include, and "
            "automodule."
        ),
        tool="inventory",
        arguments={
            "entries": [
                {
                    "path": "index.rst",
                    "content": (
                        "Welcome\n"
                        "=======\n\n"
                        ".. note::\n"
                        "   Pinned note.\n\n"
                        ".. include:: partial.rst\n\n"
                        ".. automodule:: pkg.module\n"
                    ),
                }
            ]
        },
        required_facts=("inventory_digest", "source_manifest_digest", "findings"),
    ),
)
