from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="acceptance-bind-leaf-320",
        prompt="Seal sprint done-criteria before implementation begins.",
        tool="bind",
        arguments={
            "acceptance_id": "leaf-320",
            "criteria": [
                {
                    "id": "pytest-leaf",
                    "statement": "issue marker green",
                    "verify": {
                        "kind": "pytest",
                        "ref": "tests/stars/test_acceptance_bind.py",
                    },
                },
                {
                    "id": "ruff",
                    "statement": "ruff check clean",
                    "verify": {
                        "kind": "command",
                        "ref": "uv run ruff check .",
                        "expect": "0",
                    },
                },
            ],
        },
        required_facts=("acceptance_digest", "sealed_at", "criteria"),
    ),
)
