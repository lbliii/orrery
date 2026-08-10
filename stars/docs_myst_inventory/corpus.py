from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="docs-myst-inventory-baseline",
        prompt="Inventory a small MyST tree with admonitions and an include directive.",
        tool="inventory",
        arguments={
            "entries": [
                {
                    "path": "index.md",
                    "content": (
                        "# Welcome\n\n"
                        "```{note}\n"
                        "Pinned note.\n"
                        "```\n\n"
                        "```{include} partial.md\n"
                        "```\n"
                    ),
                }
            ]
        },
        required_facts=("inventory_digest", "source_manifest_digest", "findings"),
    ),
)
