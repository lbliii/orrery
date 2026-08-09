from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="ship-httpx",
        prompt="Run a ship check for httpx.",
        tool="run",
        arguments={"package": "httpx"},
        required_facts=("ready_to_reason", "source_watch", "utc"),
    ),
)
