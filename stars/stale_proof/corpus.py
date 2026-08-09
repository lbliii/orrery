from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="stale-proof-live-evidence",
        prompt="Seal fresh UTC and Python release-note evidence.",
        tool="run",
        arguments={},
        required_facts=("orrery/stale-proof", "source_watch", "world_time", "limitations"),
    ),
)
