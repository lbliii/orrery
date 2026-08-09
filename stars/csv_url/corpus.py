from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="vega-flights-airport-csv",
        prompt="Get a typed sample of the Vega flights-airport CSV dataset.",
        tool="get",
        arguments={"dataset": "flights-airport"},
        required_facts=("raw.githubusercontent.com", "source_digest", "schema", "rows"),
    ),
)
