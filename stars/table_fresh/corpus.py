from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="table-fresh",
        prompt="Freshen and compare a baseline.",
        tool="run",
        arguments={"baseline": {"rows": [{"origin": "ABE", "destination": "ATL", "count": 853}]}},
        required_facts=("bounded_sample", "source_digest", "changed_count"),
    ),
)
