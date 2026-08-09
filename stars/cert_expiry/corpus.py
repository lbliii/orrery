from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="cert-expiry-orrery",
        prompt="Check the TLS certificate expiry for Orrery's public host.",
        tool="inspect",
        arguments={"host": "orrery-public"},
        required_facts=("orrery.lol", "not_after", "days_until_expiry", "sha256_fingerprint"),
    ),
)
