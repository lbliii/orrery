from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="pep-8-introduction",
        prompt="Get PEP 8 Introduction.",
        tool="get",
        arguments={"pep": "8", "section": "Introduction"},
        required_facts=("peps.python.org", "source_digest", "slice_digest", "text_slice"),
    ),
)
