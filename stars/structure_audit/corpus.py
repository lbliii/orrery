from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="structure-audit-clean-readme",
        prompt="Audit this markdown set for structure findings.",
        tool="audit",
        arguments={
            "files": [
                {
                    "path": "docs/readme.md",
                    "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
                }
            ]
        },
        required_facts=("findings", "finding_codes", "file_count"),
    ),
)
