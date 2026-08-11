from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="migration-git-handoff-digest-receipt",
        prompt=(
            "Verify this sealed migration bundle and emit a digest-only Git handoff "
            "receipt for a caller-local checkout."
        ),
        tool="handoff",
        arguments={
            "profile": {"profile_id": "docs/myst-to-mdx-baseline"},
            "change_bundle": {"bundle_digest": "a" * 64},
            "repo_identity_policy": {"policy": "orrery/checkout-roots@v1"},
            "checkout_root": "workspace/demo",
            "authority": {"policy": "orrery/migration-handoff@v1"},
            "local_validation": {"validation_digest": "b" * 64, "passed": True},
            "branch_or_pr_ref": {"branch": "migration/docs-mdx"},
        },
        required_facts=("handoff_receipt", "authorized"),
    ),
)
