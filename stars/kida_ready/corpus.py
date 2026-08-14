from chirp.skill.smoke import CorpusPrompt

from stars.kida_check.corpus import _BADGE_TEMPLATE as _BADGE_TYPO_TEMPLATE
from stars.kida_render.corpus import _BADGE_TEMPLATE as _BADGE_FIXED_TEMPLATE

_BADGE_DATA = {"count": 5, "label": "Messages"}

CORPUS = (
    CorpusPrompt(
        id="kida-ready-badge-typo",
        prompt=(
            "Run the kida-ready constellation on a badge template with a call-site typo."
        ),
        tool="run",
        arguments={
            "templates": [
                {
                    "path": "templates/dashboard.html",
                    "content": _BADGE_TYPO_TEMPLATE,
                }
            ],
            "data": _BADGE_DATA,
            "validate_calls": True,
            "strict": False,
        },
        required_facts=("orrery/kida-ready", "disposition", "stages"),
    ),
    CorpusPrompt(
        id="kida-ready-badge-ready",
        prompt="Run the kida-ready constellation on a fixed badge template and data.",
        tool="run",
        arguments={
            "templates": [
                {
                    "path": "templates/dashboard.html",
                    "content": _BADGE_FIXED_TEMPLATE,
                }
            ],
            "data": _BADGE_DATA,
            "validate_calls": True,
            "strict": False,
        },
        required_facts=("orrery/kida-ready", "disposition", "stages"),
    ),
)
