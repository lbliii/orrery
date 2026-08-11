"""Docs migrate-to-MDX resumable constellation (ADR 0007/0008, #178).

Frozen stage graph: inventory → choose-profile → safe-convert →
unsupported-decision (pause when needed) → validate-diff → artifact-seal.
Consumes sealed shapes from migration stars — does not reimplement them.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from chirp.skill import sign_envelope

from catalog.constellation import policy_for
from catalog.constellation_run import (
    ActionRequest,
    CheckpointRecord,
    ConstellationRunError,
    cancel_checkpoint,
    checkpoint_status_payload,
    default_action_expires_at,
    get_run_store,
    payload_digest_for,
    policy_digest_full,
    release_identity,
    stage_receipt_digest,
    status_for_run,
)
from stars._core.migration_profile import MigrationProfileError, require_profile
from stars._core.migration_receipt import seal_migration_receipt
from stars.decision_bind.service import bind as bind_decision
from stars.docs_mdx_validate_and_migration_diff.service import validate as validate_migration
from stars.docs_myst_inventory.service import inventory as build_inventory
from stars.docs_myst_to_mdx_safe.service import apply as safe_apply
from stars.docs_myst_to_mdx_safe.service import plan as safe_plan

CONSTELLATION = "orrery/docs-migrate-to-mdx"
DISPOSITIONS = (
    "completed",
    "awaiting_input",
    "inconclusive",
    "failed",
    "cancelled",
    "expired",
)
ACTION_KIND = "unsupported_semantics_decision"
DECISION_ACTIONS = frozenset({"hold", "abort"})
ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "feature_id": {"type": "string", "minLength": 1},
                    "action": {"type": "string", "enum": sorted(DECISION_ACTIONS)},
                },
                "required": ["feature_id", "action"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["decisions"],
    "additionalProperties": False,
}
_COMPONENTS = (
    {"name": "orrery/docs-myst-inventory", "version": "0.1.0"},
    {"name": "orrery/docs-myst-to-mdx-safe", "version": "0.1.0"},
    {"name": "orrery/docs-mdx-validate-and-migration-diff", "version": "0.1.0"},
)
_LIMITATIONS = (
    "Frozen migration graph — inventory/convert/validate stars are consumed, not reimplemented.",
    "Pause only for decision_required semantics; safe corpus may complete synchronously.",
    "Default receipts bind digests only — no raw private source bytes (ADR 0008).",
    "Duplicate continue_run replays the same composite — no second patch.",
    "Waiting never holds a worker/MCP/HTTP lease (ADR 0007 lease_rule).",
)


def run(
    entries: object,
    profile: object,
    *,
    caller_id: object = "anonymous",
    skill_name: str = "docs-migrate-to-mdx",
    skill_version: str = "0.1.0",
    key_id: str = "orrery-docs-migrate-to-mdx-1",
    private_key: Any = None,
) -> dict[str, Any]:
    """Start a docs/migrate-to-mdx run through inventory, profile pin, and safe convert."""
    if not isinstance(caller_id, str) or not caller_id.strip():
        return {"error": "caller_id_invalid", "status": "invalid"}
    if private_key is None:
        return {"error": "signing_key_required", "status": "invalid"}

    normalized, entry_error = _normalize_entries(entries)
    if entry_error is not None:
        return entry_error
    pinned, profile_error = _pin_profile(profile)
    if profile_error is not None:
        return profile_error
    assert normalized is not None and pinned is not None

    graph = policy_for(CONSTELLATION)
    if graph is None:
        return {"error": "policy_missing", "constellation": CONSTELLATION}

    gate_result, gate_error = _run_through_safe_convert(normalized, pinned)
    if gate_error is not None:
        return gate_error
    assert gate_result is not None

    stage_digests = list(gate_result["stage_receipt_digests"])
    bundle = {
        "entries": normalized,
        "profile": pinned,
        **gate_result["artifacts"],
    }

    decision_findings = _decision_required_findings(gate_result["findings"])
    if not decision_findings:
        return _seal_terminal(
            caller_id=caller_id.strip(),
            run_id=secrets.token_urlsafe(12),
            bundle=bundle,
            stage_receipt_digests=tuple(stage_digests),
            decisions=(),
            skill_name=skill_name,
            skill_version=skill_version,
            key_id=key_id,
            private_key=private_key,
            graph=graph,
            paused=False,
        )

    run_id = secrets.token_urlsafe(12)
    request_id = secrets.token_urlsafe(8)
    required_ids = sorted({str(item["feature_id"]) for item in decision_findings})
    action_request = ActionRequest(
        request_id=request_id,
        run_id=run_id,
        kind=ACTION_KIND,
        schema=dict(ACTION_SCHEMA),
        audience="decision_maker",
        expires_at=default_action_expires_at(),
        title="Unsupported MyST semantics require a decision",
        prompt=(
            "Choose hold (proceed with preserved syntax) or abort for each "
            f"decision_required feature: {', '.join(required_ids)}."
        ),
    )

    record = CheckpointRecord(
        run_id=run_id,
        caller_id=caller_id.strip(),
        constellation=CONSTELLATION,
        disposition="awaiting_input",
        policy_digest=policy_digest_full(CONSTELLATION, graph),
        release=release_identity(graph),
        graph_position="unsupported-decision",
        stage_receipt_digests=tuple(stage_digests),
        outstanding_action_requests=(action_request,),
        bundle={
            **bundle,
            "required_feature_ids": required_ids,
        },
        lease_held=False,
    )
    get_run_store().put_checkpoint(record)
    return checkpoint_status_payload(record)


def status(run_id: str = "") -> dict[str, Any]:
    """Read-only run disposition and outstanding action requests."""
    return status_for_run(run_id)


def continue_run(
    run_id: object,
    request_id: object,
    response: object,
    *,
    caller_id: object = "anonymous",
    skill_name: str = "docs-migrate-to-mdx",
    skill_version: str = "0.1.0",
    key_id: str = "orrery-docs-migrate-to-mdx-1",
    private_key: Any = None,
) -> dict[str, Any]:
    """Resume a paused migration run and seal the composite receipt (idempotent)."""
    if not isinstance(run_id, str) or not run_id.strip():
        return {"error": "run_id_invalid", "status": "invalid"}
    if not isinstance(request_id, str) or not request_id.strip():
        return {"error": "request_id_invalid", "status": "invalid"}
    if not isinstance(caller_id, str) or not caller_id.strip():
        return {"error": "caller_id_invalid", "status": "invalid"}
    if private_key is None:
        return {"error": "signing_key_required", "status": "invalid"}

    store = get_run_store()
    record = store.get_checkpoint(run_id.strip())
    if record is None:
        return {"error": "not_found", "run_id": run_id, "status": "not_found"}
    if record.caller_id != caller_id.strip():
        return {"error": "forbidden", "run_id": run_id, "status": "forbidden"}
    if record.disposition == "completed" and record.composite is not None:
        return {**record.composite, "replayed": True}

    if record.disposition != "awaiting_input":
        return checkpoint_status_payload(record)

    outstanding = record.outstanding_action_requests
    if len(outstanding) != 1:
        return {"error": "action_request_count", "expected": 1, "got": len(outstanding)}
    action = outstanding[0]
    if action.request_id != request_id.strip():
        return {
            "error": "request_id_mismatch",
            "expected": action.request_id,
            "got": request_id,
        }

    parsed, parse_error = _parse_decision_response(
        response,
        required_feature_ids=tuple(record.bundle.get("required_feature_ids") or ()),
    )
    if parse_error is not None:
        return parse_error

    if _action_expired(action.expires_at):
        expired = _replace_disposition(record, "expired")
        store.put_checkpoint(expired)
        return checkpoint_status_payload(expired)

    assert parsed is not None
    if any(item["action"] == "abort" for item in parsed["decisions"]):
        failed = CheckpointRecord(
            run_id=record.run_id,
            caller_id=record.caller_id,
            constellation=record.constellation,
            disposition="failed",
            policy_digest=record.policy_digest,
            release=dict(record.release),
            graph_position="unsupported-decision",
            stage_receipt_digests=record.stage_receipt_digests,
            outstanding_action_requests=(),
            bundle=dict(record.bundle),
            lease_held=False,
        )
        store.put_checkpoint(failed)
        return checkpoint_status_payload(failed)

    graph = policy_for(CONSTELLATION)
    if graph is None:
        return {"error": "policy_missing", "constellation": CONSTELLATION}

    def _complete() -> dict[str, Any]:
        return _seal_terminal(
            caller_id=record.caller_id,
            run_id=record.run_id,
            bundle=dict(record.bundle),
            stage_receipt_digests=record.stage_receipt_digests,
            decisions=tuple(parsed["decisions"]),
            skill_name=skill_name,
            skill_version=skill_version,
            key_id=key_id,
            private_key=private_key,
            graph=graph,
            paused=True,
        )

    try:
        result = store.seal_continuation(
            caller_id=caller_id.strip(),
            run_id=record.run_id,
            request_id=action.request_id,
            payload=parsed,
            producer=_complete,
        )
    except ConstellationRunError as error:
        return {"error": str(error), "run_id": record.run_id, "status": "invalid"}

    if not result.get("replayed"):
        completed = CheckpointRecord(
            run_id=record.run_id,
            caller_id=record.caller_id,
            constellation=record.constellation,
            disposition="completed",
            policy_digest=record.policy_digest,
            release=dict(record.release),
            graph_position="artifact-seal",
            stage_receipt_digests=tuple(result.get("stage_receipt_digests", ())),
            outstanding_action_requests=(),
            bundle=dict(record.bundle),
            chain=tuple(result.get("chain_steps", ())),
            composite=result,
            artifact_digest=str(result.get("artifact_digest", "")),
            lease_held=False,
            cites=tuple(result.get("cites") or ()),
        )
        store.put_checkpoint(completed)
    return result


def cancel(run_id: str, *, caller_id: str = "anonymous") -> dict[str, Any]:
    """Cancel a paused or in-flight migration run."""
    return cancel_checkpoint(run_id, caller_id=caller_id)


def _run_through_safe_convert(
    entries: list[dict[str, str]],
    profile: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    inventory_result = build_inventory(entries)
    if "error" in inventory_result:
        return None, dict(inventory_result)

    inventory_stage = {
        "stage": "inventory",
        "inventory_digest": inventory_result["inventory_digest"],
        "source_manifest_digest": inventory_result["source_manifest_digest"],
        "entry_count": inventory_result["entry_count"],
    }
    profile_stage = {
        "stage": "choose-profile",
        "profile_id": profile["profile_id"],
        "profile_version": profile["version"],
        "profile_digest": profile["profile_digest"],
    }

    plan_result = safe_plan(entries, profile)
    if "error" in plan_result:
        return None, dict(plan_result)

    apply_result = safe_apply(entries, plan_result, profile)
    if "error" in apply_result:
        return None, dict(apply_result)

    convert_stage = {
        "stage": "safe-convert",
        "plan_digest": plan_result["plan_digest"],
        "bundle_digest": apply_result["bundle_digest"],
        "entry_count": apply_result["entry_count"],
    }

    stage_digests = (
        stage_receipt_digest(inventory_stage),
        stage_receipt_digest(profile_stage),
        stage_receipt_digest(convert_stage),
    )
    findings = list(inventory_result["findings"])
    return {
        "stage_receipt_digests": stage_digests,
        "findings": findings,
        "artifacts": {
            "inventory": inventory_result,
            "plan": plan_result,
            "apply": apply_result,
            "targets": apply_result["targets"],
            "change_bundle": apply_result["change_bundle"],
        },
    }, None


def _seal_terminal(
    *,
    caller_id: str,
    run_id: str,
    bundle: Mapping[str, Any],
    stage_receipt_digests: tuple[str, ...],
    decisions: tuple[Mapping[str, str], ...],
    skill_name: str,
    skill_version: str,
    key_id: str,
    private_key: Any,
    graph: Any,
    paused: bool,
) -> dict[str, Any]:
    profile = dict(bundle["profile"])
    entries = list(bundle["entries"])
    inventory_result = dict(bundle["inventory"])
    plan_result = dict(bundle["plan"])
    apply_result = dict(bundle["apply"])
    targets = list(bundle["targets"])
    change_bundle = dict(bundle["change_bundle"])

    validation_result = validate_migration(
        source_entries=entries,
        target_entries=targets,
        change_bundle=change_bundle,
        profile=profile,
        plan=plan_result,
    )
    if "error" in validation_result:
        return dict(validation_result)

    validation_stage = {
        "stage": "validate-diff",
        "validation_digest": validation_result["validation_digest"],
        "validation_passed": validation_result["validation_passed"],
        "report_digest": validation_result["report_digest"],
    }

    cites: list[str] = []
    decision_stage_digest: str | None = None
    if decisions:
        decision_rows = []
        for item in decisions:
            feature_id = str(item["feature_id"])
            action = str(item["action"])
            bound = bind_decision(
                f"myst-{feature_id}",
                f"Proceed with action={action} for unsupported feature {feature_id}.",
            )
            if "error" in bound:
                return dict(bound)
            cites.append(str(bound["decision_digest"]))
            decision_rows.append(
                {
                    "feature_id": feature_id,
                    "action": action,
                    "decision_digest": bound["decision_digest"],
                }
            )
        decision_stage = {
            "stage": "unsupported-decision",
            "decisions": decision_rows,
        }
        decision_stage_digest = stage_receipt_digest(decision_stage)

    stage_outputs = {
        "analyze": inventory_result,
        "plan": plan_result,
        "apply": apply_result,
        "validate": validation_result["validation"],
    }
    sealed = seal_migration_receipt(
        profile,
        mode="validate",
        source_manifest_digest=str(inventory_result["source_manifest_digest"]),
        stage_outputs=stage_outputs,
        validation=validation_result["validation"],
        cites=cites or None,
    )
    if "error" in sealed:
        return dict(sealed)

    migration_receipt = dict(sealed["receipt"])
    output_manifest_digest = _output_manifest_digest(targets)

    all_stage_digests = list(stage_receipt_digests)
    if decision_stage_digest is not None:
        all_stage_digests.append(decision_stage_digest)
    all_stage_digests.append(stage_receipt_digest(validation_stage))
    seal_stage = {
        "stage": "artifact-seal",
        "receipt_digest": migration_receipt["receipt_digest"],
        "output_manifest_digest": output_manifest_digest,
    }
    all_stage_digests.append(stage_receipt_digest(seal_stage))

    bundle_digest = stage_receipt_digest(
        {
            "source_manifest_digest": inventory_result["source_manifest_digest"],
            "profile_digest": profile["profile_digest"],
            "entry_count": len(entries),
        }
    )
    seal_envelope = sign_envelope(
        payload={
            "gate": "artifact-seal",
            "verdict": "pass",
            "receipt_digest": migration_receipt["receipt_digest"],
            "validation_passed": validation_result["validation_passed"],
            "bundle_digest": apply_result["bundle_digest"],
        },
        skill=skill_name,
        version=skill_version,
        tool="continue_run" if paused else "run",
        input_digest=bundle_digest,
        private_key=private_key,
        key_id=key_id,
        nonce=f"{run_id}-seal",
    ).to_wire()

    chain_steps = _chain_steps(
        stage_receipt_digests=stage_receipt_digests,
        decision_stage_digest=decision_stage_digest,
        validation_stage_digest=all_stage_digests[-2],
        seal_stage_digest=all_stage_digests[-1],
        seal_envelope=seal_envelope,
        paused=paused,
    )

    composite: dict[str, Any] = {
        "run_id": run_id,
        "constellation": CONSTELLATION,
        "disposition": "completed",
        "chain": "signed-envelope-chain",
        "policy_digest": policy_digest_full(CONSTELLATION, graph),
        "release": release_identity(graph),
        "stages": {
            "inventory": {
                "inventory_digest": inventory_result["inventory_digest"],
                "source_manifest_digest": inventory_result["source_manifest_digest"],
            },
            "choose-profile": {
                "profile_id": profile["profile_id"],
                "profile_digest": profile["profile_digest"],
            },
            "safe-convert": {
                "plan_digest": plan_result["plan_digest"],
                "bundle_digest": apply_result["bundle_digest"],
            },
            "validate-diff": {
                "validation_digest": validation_result["validation_digest"],
                "validation_passed": validation_result["validation_passed"],
            },
            "artifact-seal": {
                "receipt_digest": migration_receipt["receipt_digest"],
                "output_manifest_digest": output_manifest_digest,
            },
        },
        "migration_receipt": migration_receipt,
        "source_manifest_digest": inventory_result["source_manifest_digest"],
        "output_manifest_digest": output_manifest_digest,
        "profile_digest": profile["profile_digest"],
        "bundle_digest": apply_result["bundle_digest"],
        "validation_digest": validation_result["validation_digest"],
        "validation_passed": validation_result["validation_passed"],
        "stage_receipt_digests": all_stage_digests,
        "artifact_digest": migration_receipt["receipt_digest"],
        "components": list(_COMPONENTS),
        "limitations": list(_LIMITATIONS),
        "lease_held": False,
        "lease_rule": "waiting_never_holds_worker_lease",
        "chain_steps": chain_steps,
    }
    if cites:
        composite["cites"] = cites
        composite["stages"]["unsupported-decision"] = {
            "decision_count": len(cites),
            "cites": cites,
        }
    store = get_run_store()
    completed = CheckpointRecord(
        run_id=run_id,
        caller_id=caller_id,
        constellation=CONSTELLATION,
        disposition="completed",
        policy_digest=composite["policy_digest"],
        release=dict(composite["release"]),
        graph_position="artifact-seal",
        stage_receipt_digests=tuple(all_stage_digests),
        outstanding_action_requests=(),
        bundle=dict(bundle),
        chain=tuple(chain_steps),
        composite=composite,
        artifact_digest=str(composite["artifact_digest"]),
        lease_held=False,
        cites=tuple(cites),
    )
    store.put_checkpoint(completed)
    return composite


def _chain_steps(
    *,
    stage_receipt_digests: tuple[str, ...],
    decision_stage_digest: str | None,
    validation_stage_digest: str,
    seal_stage_digest: str,
    seal_envelope: dict[str, Any],
    paused: bool,
) -> list[dict[str, Any]]:
    labels = ["inventory", "choose-profile", "safe-convert"]
    steps: list[dict[str, Any]] = []
    order = 1
    for label, digest in zip(labels, stage_receipt_digests, strict=True):
        steps.append(
            {
                "order": order,
                "label": label,
                "status": "Envelope ✓",
                "stage_receipt_digest": digest,
            }
        )
        order += 1
    if decision_stage_digest is not None:
        steps.append(
            {
                "order": order,
                "label": "unsupported-decision",
                "status": "Envelope ✓",
                "stage_receipt_digest": decision_stage_digest,
            }
        )
        order += 1
    elif not paused:
        steps.append(
            {
                "order": order,
                "label": "unsupported-decision",
                "status": "skipped",
                "note": "no decision_required findings",
            }
        )
        order += 1
    steps.extend(
        [
            {
                "order": order,
                "label": "validate-diff",
                "status": "Envelope ✓",
                "stage_receipt_digest": validation_stage_digest,
            },
            {
                "order": order + 1,
                "label": "artifact-seal",
                "status": "Envelope ✓",
                "envelope": seal_envelope,
                "stage_receipt_digest": seal_stage_digest,
            },
        ]
    )
    return steps


def _output_manifest_digest(targets: Sequence[Mapping[str, str]]) -> str:
    rows = sorted(
        (
            {
                "path": item["path"],
                "content_digest": payload_digest_for({"content": item["content"]}),
            }
            for item in targets
        ),
        key=lambda row: row["path"],
    )
    return stage_receipt_digest({"targets": rows})


def _decision_required_findings(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in findings
        if item.get("class") == "decision_required"
    ]


def _normalize_entries(
    entries: object,
) -> tuple[list[dict[str, str]] | None, dict[str, Any] | None]:
    if entries is None:
        return None, {"error": "entries_required", "status": "invalid"}
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return None, {"error": "entries_invalid", "status": "invalid"}

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, Mapping):
            return None, {"error": "entry_invalid", "status": "invalid"}
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path.strip():
            return None, {"error": "path_invalid", "path": path, "status": "invalid"}
        if not isinstance(content, str):
            return None, {"error": "content_invalid", "path": path, "status": "invalid"}
        if path in seen:
            return None, {"error": "path_duplicate", "path": path, "status": "invalid"}
        seen.add(path)
        normalized.append({"path": path, "content": content})

    if not normalized:
        return None, {"error": "entries_empty", "status": "invalid"}
    normalized.sort(key=lambda entry: entry["path"])
    return normalized, None


def _pin_profile(profile: object) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if profile is None:
        return None, {"error": "profile_required", "status": "invalid"}
    if not isinstance(profile, Mapping):
        return None, {"error": "profile_invalid", "status": "invalid"}
    try:
        pinned = require_profile(profile)
    except MigrationProfileError as exc:
        return None, {"error": "profile_invalid", "detail": str(exc), "status": "invalid"}
    return dict(pinned), None


def _parse_decision_response(
    response: object,
    *,
    required_feature_ids: tuple[str, ...],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not isinstance(response, Mapping):
        return {}, {"error": "response_invalid", "status": "invalid"}
    raw_decisions = response.get("decisions")
    if not isinstance(raw_decisions, list) or not raw_decisions:
        return {}, {"error": "decisions_required", "status": "invalid"}

    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_decisions:
        if not isinstance(item, Mapping):
            return {}, {"error": "decision_invalid", "status": "invalid"}
        feature_id = item.get("feature_id")
        action = item.get("action")
        if not isinstance(feature_id, str) or not feature_id.strip():
            return {}, {"error": "feature_id_invalid", "status": "invalid"}
        if not isinstance(action, str) or action not in DECISION_ACTIONS:
            return {}, {"error": "action_invalid", "status": "invalid"}
        if feature_id in seen:
            return {}, {"error": "feature_id_duplicate", "status": "invalid"}
        seen.add(feature_id)
        parsed.append({"feature_id": feature_id, "action": action})

    required = set(required_feature_ids)
    if seen != required:
        return {}, {
            "error": "decisions_incomplete",
            "expected": sorted(required),
            "received": sorted(seen),
            "status": "invalid",
        }
    parsed.sort(key=lambda row: row["feature_id"])
    return {"decisions": parsed}, None


def _action_expired(expires_at: str) -> bool:
    try:
        deadline = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return datetime.now(tz=UTC) >= deadline


def _replace_disposition(record: CheckpointRecord, disposition: str) -> CheckpointRecord:
    return CheckpointRecord(
        run_id=record.run_id,
        caller_id=record.caller_id,
        constellation=record.constellation,
        disposition=disposition,  # type: ignore[arg-type]
        policy_digest=record.policy_digest,
        release=dict(record.release),
        graph_position=record.graph_position,
        stage_receipt_digests=record.stage_receipt_digests,
        outstanding_action_requests=(),
        bundle=dict(record.bundle),
        chain=record.chain,
        lease_held=False,
        cites=record.cites,
    )
