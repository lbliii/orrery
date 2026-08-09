from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="flight-abe-atl",
        prompt="Look up the ABE to ATL aggregate flight count.",
        tool="lookup",
        arguments={"dataset": "flights-airport", "key": {"origin": "ABE", "destination": "ATL"}},
        required_facts=("source_digest", "canonical_url", "row", "rows_scanned"),
    ),
)
