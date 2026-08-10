from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="docs-mdx-validate-and-migration-diff-safe",
        prompt=(
            "Validate sealed MDX targets from a safe MyST transform and emit "
            "migration-diff evidence under the pinned docs profile."
        ),
        tool="validate",
        arguments={
            "source_entries": [
                {
                    "path": "index.md",
                    "content": (
                        "# Welcome\n\n"
                        "```{note}\n"
                        "Pinned note.\n"
                        "```\n"
                    ),
                }
            ],
            "target_entries": [
                {
                    "path": "index.md",
                    "content": (
                        "# Welcome\n\n"
                        '<Admonition type="note">\n'
                        "Pinned note.\n"
                        "</Admonition>\n"
                    ),
                }
            ],
            "change_bundle": {
                "plan_digest": "1" * 64,
                "patch_digest": "2" * 64,
                "file_entries": [
                    {
                        "path": "index.md",
                        "source_digest": "3" * 64,
                        "target_digest": "4" * 64,
                    }
                ],
                "mapping_digest": "5" * 64,
                "warnings": [],
                "bundle_digest": (
                    "f6201ba718756c8fb29f76ffa21a1d5e"
                    "7bcd8a222bcc7937bda1b52ac132cd86"
                ),
            },
            "profile": {
                "schema_version": "migration-profile/v1",
                "profile_id": "docs/myst-to-mdx-baseline",
                "version": "1.0.0",
                "source": {"kind": "myst-markdown", "version": "1.3.0"},
                "target": {"kind": "mdx", "version": "3.0.0"},
                "feature_vocabulary": {
                    "supported": [
                        {"id": "md.heading", "class": "safe"},
                        {"id": "myst.directive.admonition", "class": "transformable"},
                    ],
                    "unsupported": [
                        {"id": "myst.directive.include", "class": "decision_required"},
                    ],
                },
                "compatibility_policy": {
                    "policy_id": "docs-mdx-baseline-v1",
                    "default_action": "report",
                    "rules": [
                        {
                            "id": "nav.link.break",
                            "severity": "breaking",
                            "action": "decision_required",
                        }
                    ],
                },
                "execution_locality": "agent_local",
                "transformer": {
                    "name": "orrery/docs-myst-to-mdx",
                    "version": "1.0.0",
                    "digest": (
                        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                    ),
                },
                "validator": {
                    "name": "orrery/docs-mdx-validate",
                    "version": "1.0.0",
                    "digest": (
                        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
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
                    "9ac8aaab94e6041edf459e96d27973a722773e0dda2fa272edb62a6be96ed82b"
                ),
            },
        },
        required_facts=(
            "validation_digest",
            "report_digest",
            "migration_diff",
            "validation_passed",
        ),
    ),
)
