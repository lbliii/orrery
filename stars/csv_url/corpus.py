from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="vega-cars-csv",
        prompt="Get a typed sample of the Vega cars CSV dataset.",
        tool="get",
        arguments={"dataset": "cars"},
        required_facts=("raw.githubusercontent.com", "source_digest", "schema", "rows"),
    ),
)
