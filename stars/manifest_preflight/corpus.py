from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="manifest-preflight-docs-only",
        prompt="Check files before run against the docs-only policy.",
        tool="check",
        arguments={
            "policy": "orrery/docs-only@v1",
            "files": [
                {
                    "path": "docs/readme.md",
                    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "size": 12,
                }
            ],
        },
        required_facts=("passed", "policy", "violation_codes"),
    ),
)
