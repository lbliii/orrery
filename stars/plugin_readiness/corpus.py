from pathlib import Path

from chirp.skill.smoke import CorpusPrompt

_PACKAGE = Path(__file__).resolve().parents[2] / "plugins" / "orrery"
_ORRERY_BUNDLE = [
    {"path": path.name, "content": path.read_text(encoding="utf-8")}
    for path in sorted(_PACKAGE.iterdir())
    if path.is_file()
]

CORPUS = (
    CorpusPrompt(
        id="plugin-readiness-orrery-package",
        prompt="Assess the official Orrery Agent Plugins package.",
        tool="run",
        arguments={"files": _ORRERY_BUNDLE},
        required_facts=("orrery/plugin-readiness", "disposition", "stages"),
    ),
)
