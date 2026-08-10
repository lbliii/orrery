from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="ship-httpx",
        prompt="Run a ship check for httpx.",
        tool="run",
        arguments={"package": "httpx"},
        required_facts=("ready_to_reason", "source_watch", "utc"),
    ),
    CorpusPrompt(
        id="ship-content-bundle",
        prompt="Run a content-bundle ship check on a docs readme.",
        tool="run",
        arguments={
            "mode": "content-bundle",
            "files": [
                {
                    "path": "docs/readme.md",
                    "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
                }
            ],
        },
        required_facts=("disposition", "stages", "manifest-bind"),
    ),
)
