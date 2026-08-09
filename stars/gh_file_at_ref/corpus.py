from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="orrery-readme-pinned",
        prompt="Get the pinned Orrery README.",
        tool="get",
        arguments={"target": "orrery-readme", "ref": "0000000000000000000000000000000000000000"},
        required_facts=("requested_ref", "blob_sha", "content_digest"),
    ),
)
