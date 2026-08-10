from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="decision-bind-myst-freeze",
        prompt="Seal a planner freeze: do not invent MDX for unsupported MyST directives.",
        tool="bind",
        arguments={
            "decision_id": "myst-directive-v1",
            "statement": (
                "pause for typed decision on unsupported MyST directive; do not invent MDX."
            ),
        },
        required_facts=("decision_digest", "decided_at", "statement"),
    ),
)
