from chirp.skill.smoke import CorpusPrompt

from stars.write_authority_check.contract import POLICY_EXPLICIT_PATHS
from stars.write_authority_check.service import grant_digest

_PATHS = ["docs/readme.md"]
_DIGEST = grant_digest(POLICY_EXPLICIT_PATHS, _PATHS)

CORPUS = (
    CorpusPrompt(
        id="authorized-content-patch-docs-edit",
        prompt="Authorize and capture a docs content patch under an explicit grant.",
        tool="run",
        arguments={
            "before": [
                {
                    "path": "docs/readme.md",
                    "content": "---\ntitle: Readme\n---\n\n# Readme\n\nHello.\n",
                }
            ],
            "after": [
                {
                    "path": "docs/readme.md",
                    "content": (
                        "---\ntitle: Readme\n---\n\n# Readme\n\n"
                        "See [Python](https://docs.python.org/3/).\n"
                    ),
                }
            ],
            "authority": {
                "policy": POLICY_EXPLICIT_PATHS,
                "allowed_paths": list(_PATHS),
                "grant_digest": _DIGEST,
            },
            "policy": "orrery/docs-only@v1",
            "max_link_count": 20,
        },
        required_facts=(
            "orrery/authorized-content-patch",
            "disposition",
            "stages",
        ),
    ),
)
