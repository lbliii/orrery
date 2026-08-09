from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="flask-latest",
        prompt="Observe the Flask latest release.",
        tool="observe",
        arguments={"target": "flask"},
        required_facts=("body_digest", "tag", "source_digest"),
    ),
)
