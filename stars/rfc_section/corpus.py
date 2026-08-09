from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="rfc-9110-section-3-1",
        prompt="Get RFC 9110 section 3.1.",
        tool="get",
        arguments={"rfc": "9110", "section": "3.1"},
        required_facts=("rfc-editor.org", "source_digest", "slice_digest", "text_slice"),
    ),
)
