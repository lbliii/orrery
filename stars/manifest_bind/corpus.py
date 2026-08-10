from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="manifest-bind-two-files",
        prompt="Bind these two file digests into a stable manifest receipt.",
        tool="bind",
        arguments={
            "files": [
                {
                    "path": "docs/readme.md",
                    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "size": 12,
                },
                {
                    "path": "docs/plan.md",
                    "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "size": 34,
                },
            ]
        },
        required_facts=("manifest_digest", "admitted_count", "excluded_count"),
    ),
)
