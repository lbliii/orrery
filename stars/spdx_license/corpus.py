from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="spdx-mit-license",
        prompt="Get the MIT license record from SPDX.",
        tool="get",
        arguments={"license_id": "MIT"},
        required_facts=("spdx.org", "license_id", "source_digest", "text_slice"),
    ),
)
