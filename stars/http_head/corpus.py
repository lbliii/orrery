from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="http-head-python-smoke",
        prompt="Check fresh HTTP headers for the Python 3.14 release notes.",
        tool="head",
        arguments={"target": "python-3.14-whatsnew"},
        required_facts=("python-3.14-whatsnew", "final_url", "status", "observed_at"),
    ),
)
