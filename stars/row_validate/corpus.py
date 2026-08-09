from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="validate-flight-row",
        prompt="Validate this flights-airport row.",
        tool="validate",
        arguments={
            "profile": "flights-airport",
            "row": {"origin": "ABE", "destination": "ATL", "count": 853},
        },
        required_facts=("valid", "profile_digest", "normalized_row"),
    ),
)
