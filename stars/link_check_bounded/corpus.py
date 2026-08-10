from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="link-check-example-ok",
        prompt="Check the example.com link in this markdown bundle stays under the cap.",
        tool="check",
        arguments={
            "files": [
                {
                    "path": "docs/readme.md",
                    "content": "See [docs](https://example.com/docs).",
                    "format": "markdown",
                }
            ],
            "max_link_count": 5,
        },
        required_facts=("link_count", "max_link_count", "links"),
    ),
)
