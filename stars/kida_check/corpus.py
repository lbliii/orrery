from chirp.skill.smoke import CorpusPrompt

_BADGE_TEMPLATE = """{% def badge(count: int, label: str) %}
<span class="badge">{{ count }} {{ label }}</span>
{% enddef %}

{{ badge(count="five", lable="Messages") }}
"""

CORPUS = (
    CorpusPrompt(
        id="kida-check-badge-typo",
        prompt="Validate this Kida template bundle for component call-site findings.",
        tool="check",
        arguments={
            "templates": [
                {
                    "path": "templates/dashboard.html",
                    "content": _BADGE_TEMPLATE,
                }
            ],
            "validate_calls": True,
            "strict": False,
        },
        required_facts=("findings", "finding_codes", "template_count", "passed"),
    ),
)
