from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="invite-ready-enrichment",
        prompt="Enrich a draft invite with clock, flight, place, and venue hours.",
        tool="run",
        arguments={},
        required_facts=(
            "orrery/invite-ready",
            "world_time",
            "flight_status",
            "geocode",
            "place_hours",
            "atlas_recommendation",
            "limitations",
        ),
    ),
)
