from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="content-readiness-docs-bundle",
        prompt="Assess this docs bundle for content readiness.",
        tool="run",
        arguments={
            "files": [
                {
                    "path": "docs/readme.md",
                    "content": (
                        "---\ntitle: Readme\n---\n\n# Readme\n\n"
                        "See [Python](https://docs.python.org/3/).\n"
                    ),
                }
            ],
            "policy": "orrery/docs-only@v1",
            "max_link_count": 20,
        },
        required_facts=("orrery/content-readiness", "disposition", "stages"),
    ),
)
