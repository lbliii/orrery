from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="npm-zod",
        prompt="Get the latest zod npm release.",
        tool="get",
        arguments={"package": "zod"},
        required_facts=("registry.npmjs.org", "version", "source_digest", "dist"),
    ),
)
