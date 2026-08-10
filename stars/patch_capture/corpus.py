from chirp.skill.smoke import CorpusPrompt

_A = "a" * 64
_B = "b" * 64

CORPUS = (
    CorpusPrompt(
        id="patch-capture-readme-edit",
        prompt="Capture patch receipt for a docs readme edit between two manifests.",
        tool="capture",
        arguments={
            "before": {
                "files": [{"path": "docs/readme.md", "sha256": _A, "size": 5, "content": "hello"}]
            },
            "after": {
                "files": [
                    {
                        "path": "docs/readme.md",
                        "sha256": _B,
                        "size": 11,
                        "content": "hello\nworld",
                    }
                ]
            },
        },
        required_facts=("patch_digest", "changed_paths", "line_stats"),
    ),
)
