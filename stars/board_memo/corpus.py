from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="board-memo-start",
        prompt="Start a board memo run that pauses for audience and recommendation.",
        tool="run",
        arguments={
            "title": "Q3 Platform Update",
            "summary": "Revenue grew 12% with stable infra costs.",
            "author": "ops",
            "caller_id": "corpus-smoke",
        },
        required_facts=(
            "orrery/board-memo",
            "awaiting_input",
            "outstanding_action_requests",
        ),
    ),
)
