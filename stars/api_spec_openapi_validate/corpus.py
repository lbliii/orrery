from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="api-spec-openapi-validate-safe-target",
        prompt=(
            "Validate an OpenAPI 3.1 target produced by the safe 3.0→3.1 upgrade "
            "profile against its sealed change_bundle."
        ),
        tool="validate",
        arguments={
            "target_entries": [
                {
                    "path": "openapi.json",
                    "content": (
                        '{"openapi":"3.1.0","info":{"title":"Demo","version":"1.0.0"},'
                        '"paths":{},"components":{"schemas":{"Pet":{"type":"object",'
                        '"properties":{"name":{"type":"string"}}}}}}'
                    ),
                }
            ],
            "change_bundle": {
                "plan_digest": "e" * 64,
                "patch_digest": "f" * 64,
                "file_entries": [
                    {
                        "path": "openapi.json",
                        "source_digest": "a" * 64,
                        "target_digest": "b" * 64,
                    }
                ],
                "mapping_digest": "c" * 64,
                "warnings": [],
                "bundle_digest": "d" * 64,
            },
            "profile": {
                "schema_version": "migration-profile/v1",
                "profile_id": "api-spec/openapi-3-0-to-3-1-safe",
                "version": "1.0.0",
                "source": {"kind": "openapi", "version": "3.0.3"},
                "target": {"kind": "openapi", "version": "3.1.0"},
                "feature_vocabulary": {"supported": [], "unsupported": []},
                "compatibility_policy": {
                    "policy_id": "openapi-client-server-v1",
                    "default_action": "report",
                    "rules": [],
                },
                "execution_locality": "agent_local",
                "transformer": {
                    "name": "orrery/openapi-upgrade-safe",
                    "version": "1.0.0",
                    "digest": "c" * 64,
                },
                "validator": {
                    "name": "orrery/openapi-validate",
                    "version": "1.0.0",
                    "digest": "d" * 64,
                },
                "retention_redaction": {
                    "receipt_includes": ["digests"],
                    "receipt_excludes_by_default": ["source_bytes", "target_bytes"],
                    "max_finding_message_bytes": 512,
                    "max_diagnostics_bytes": 65536,
                },
                "profile_digest": "0" * 64,
            },
        },
        required_facts=("validation_digest", "validation_passed", "validator"),
    ),
)
