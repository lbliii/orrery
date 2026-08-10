from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="docs-frontmatter-link-asset-migrate-baseline",
        prompt=(
            "Rename a frontmatter field and rewrite an internal link under "
            "explicit redirects without fetching remotes."
        ),
        tool="migrate",
        arguments={
            "entries": [
                {
                    "path": "index.md",
                    "content": (
                        "---\n"
                        "summary: Intro\n"
                        "---\n\n"
                        "# Intro\n\n"
                        "See [guide](./guide.md).\n"
                    ),
                },
                {
                    "path": "guide.md",
                    "content": "# Guide\n",
                },
            ],
            "rules": {
                "field_renames": {"summary": "description"},
                "path_redirects": {},
            },
        },
        required_facts=("migrate_digest", "patch_digest", "report", "findings"),
    ),
)
