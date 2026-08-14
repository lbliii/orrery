from chirp.skill.smoke import CorpusPrompt

_BADGE_TEMPLATE = """{% def badge(count: int, label: str) %}
<span class="badge">{{ count }} {{ label }}</span>
{% enddef %}

{{ badge(count=count, label=label) }}
"""

CORPUS = (
    CorpusPrompt(
        id="kida-render-badge",
        prompt="Render this Kida badge component with JSON data to HTML.",
        tool="render",
        arguments={
            "template": _BADGE_TEMPLATE,
            "data": {"count": 5, "label": "Messages"},
            "surface": "html",
        },
        required_facts=(
            "html",
            "surface",
            "template_digest",
            "data_digest",
            "output_digest",
        ),
    ),
)
