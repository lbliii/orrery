from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="api-spec-openapi-upgrade-safe-bump",
        prompt="Plan then apply a pinned OpenAPI 3.0.3→3.1.0 safe schema upgrade.",
        tool="plan",
        arguments={
            "entries": [
                {
                    "path": "openapi.json",
                    "content": (
                        '{\n  "openapi": "3.0.3",\n'
                        '  "info": {"title": "Demo", "version": "1.0.0"},\n'
                        '  "paths": {},\n'
                        '  "components": {"schemas": {"Pet": {"type": "object",'
                        '"properties": {"name": {"type": "string"}}}}}\n}'
                    ),
                }
            ],
            "profile": {
                "schema_version": "migration-profile/v1",
                "profile_id": "api-spec/openapi-3-0-to-3-1-safe",
                "version": "1.0.0",
                "source": {"kind": "openapi", "version": "3.0.3"},
                "target": {"kind": "openapi", "version": "3.1.0"},
                "feature_vocabulary": {
                    "supported": [
                        {"id": "openapi.json_schema.draft2020", "class": "transformable"}
                    ],
                    "unsupported": [
                        {"id": "openapi.discriminator.mapping", "class": "unsupported"}
                    ],
                },
                "compatibility_policy": {
                    "policy_id": "openapi-client-server-v1",
                    "default_action": "report",
                    "rules": [
                        {
                            "id": "breaking.path.remove",
                            "severity": "breaking",
                            "action": "block",
                        }
                    ],
                },
                "execution_locality": "agent_local",
                "transformer": {
                    "name": "orrery/openapi-upgrade-safe",
                    "version": "1.0.0",
                    "digest": (
                        "cccccccccccccccccccccccccccccccc"
                        "cccccccccccccccccccccccccccccccc"
                    ),
                },
                "validator": {
                    "name": "orrery/openapi-validate",
                    "version": "1.0.0",
                    "digest": (
                        "dddddddddddddddddddddddddddddddd"
                        "dddddddddddddddddddddddddddddddd"
                    ),
                },
                "retention_redaction": {
                    "receipt_includes": [
                        "digests",
                        "safe_metadata",
                        "tool_versions",
                        "findings_summary",
                    ],
                    "receipt_excludes_by_default": [
                        "source_bytes",
                        "target_bytes",
                        "full_patch_text",
                        "private_paths",
                    ],
                    "max_finding_message_bytes": 512,
                    "max_diagnostics_bytes": 65536,
                },
                "profile_digest": (
                    "3b28715a83ef94fd4adfc81b98f2d938327bc8236eddd8efa6e39491f2b24339"
                ),
            },
        },
        required_facts=("plan_digest", "analysis_digest", "findings"),
    ),
)
