from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="write-authority-explicit-paths",
        prompt="Check whether this write grant covers the docs paths under the manifest.",
        tool="check",
        arguments={
            "manifest_digest": (
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
            "authority": {
                "policy": "orrery/explicit-paths@v1",
                "allowed_paths": ["docs/plan.md", "docs/readme.md"],
                "grant_digest": (
                    "07bf0ad140deaed04111ea9664cd9ffd2f74fdae15c83c7e8b5ffd03b0b66750"
                ),
            },
        },
        required_facts=("authorized", "codes", "grant_digest"),
    ),
)
