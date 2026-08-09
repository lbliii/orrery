from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="well-known-llms",
        prompt="Read Orrery's official llms document.",
        tool="read",
        arguments={"document": "orrery-llms"},
        required_facts=("canonical_url", "content_digest", "text_slice", "observed_at"),
    ),
)
