from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="pypi-httpx",
        prompt="Get the current httpx PyPI release.",
        tool="get",
        arguments={"package": "httpx"},
        required_facts=("pypi.org", "version", "source_digest", "artifacts"),
    ),
)
