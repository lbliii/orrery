from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="api-spec-compatibility-diff-breaking-path",
        prompt=(
            "Diff a source OpenAPI document against a target that removes /pets "
            "under openapi-client-server-v1."
        ),
        tool="diff",
        arguments={
            "source_entries": [
                {
                    "path": "openapi.json",
                    "content": (
                        '{"openapi":"3.0.3","info":{"title":"Demo","version":"1.0.0"},'
                        '"paths":{"/pets":{"get":{"operationId":"listPets",'
                        '"responses":{"200":{"description":"ok"}}}}},'
                        '"components":{"schemas":{"Pet":{"type":"object"}}}}'
                    ),
                }
            ],
            "target_entries": [
                {
                    "path": "openapi.json",
                    "content": (
                        '{"openapi":"3.0.3","info":{"title":"Demo","version":"1.0.0"},'
                        '"paths":{},"components":{"schemas":{"Pet":{"type":"object"}}}}'
                    ),
                }
            ],
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
        },
        required_facts=("diff_digest", "changes", "policy_id", "runtime_compatibility_claimed"),
    ),
)
