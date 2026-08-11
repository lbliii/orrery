from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="docs-migrate-to-mdx-safe-complete",
        prompt="Run the safe MyST→MDX migration graph on a corpus-backed tree.",
        tool="run",
        arguments={
            "entries": [
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
            "caller_id": "corpus-smoke",
        },
        required_facts=(
            "orrery/docs-migrate-to-mdx",
            "completed",
            "migration_receipt",
        ),
    ),
)
