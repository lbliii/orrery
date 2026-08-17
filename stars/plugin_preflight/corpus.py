from chirp.skill.smoke import CorpusPrompt

from .contract import PLUGIN_SCHEMA_ID, PROFILE_V1

_MINIMAL_PLUGIN = (
    "{\n"
    f'  "$schema": "{PLUGIN_SCHEMA_ID}",\n'
    '  "name": "minimal-plugin"\n'
    "}\n"
)

CORPUS = (
    CorpusPrompt(
        id="plugin-preflight-minimal",
        prompt="Preflight this Agent Plugins 1.0.0 bundle.",
        tool="check",
        arguments={
            "profile": PROFILE_V1,
            "files": [{"path": "plugin.json", "content": _MINIMAL_PLUGIN}],
        },
        required_facts=("passed", "profile", "violation_codes"),
    ),
)
