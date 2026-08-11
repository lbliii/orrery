"""Board-memo resumable constellation (ADR 0007 Example 2 / #154).

Frozen planner subgraph: memo-bind → audience-choice pause → pdf-seal composite.
Waiting never holds a worker or MCP lease.
"""

from __future__ import annotations

import html
import secrets
from collections.abc import Mapping
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
from stars.html_to_pdf.service import convert as html_to_pdf

CONSTELLATION = "orrery/board-memo"
DISPOSITIONS = (
    "completed",
    "awaiting_input",
    "inconclusive",
    "failed",
    "cancelled",
    "expired",
)
AUDIENCES = frozenset({"board", "executive", "investor"})
RECOMMENDATIONS = frozenset({"approve", "revise", "defer"})
ACTION_KIND = "audience_recommendation_choice"
ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "audience": {"type": "string", "enum": sorted(AUDIENCES)},
        "recommendation": {"type": "string", "enum": sorted(RECOMMENDATIONS)},
    },
    "required": ["audience", "recommendation"],
}
_COMPONENTS = (
    {"name": "orrery/html-to-pdf", "version": "0.1.0"},
)
_LIMITATIONS = (
    "Dogfood resumable demo — one typed audience/recommendation pause only.",
    "PDF artifact digest is sealed; raw bytes are returned only on terminal continue.",
    "Waiting never holds a worker/MCP/HTTP lease (ADR 0007 lease_rule).",
    "Duplicate continue_run replays the same composite — no second artifact.",
)


def run(
    title: object,
    summary: object,
    *,
    author: object = "",
    caller_id: object = "anonymous",
    skill_name: str = "board-memo",
    skill_version: str = "0.1.0",
    key_id: str = "orrery-board-memo-1",
    private_key: Any = None,
) -> dict[str, Any]:
    """Start a board-memo run; pauses at audience-choice with one action_request."""
    if not isinstance(caller_id, str) or not caller_id.strip():
        return {"error": "caller_id_invalid", "status": "invalid"}
    if private_key is None:
        return {"error": "signing_key_required", "status": "invalid"}

    bundle, bind_error = _parse_bundle(title, summary, author)
    if bind_error is not None:
        return bind_error

    graph = policy_for(CONSTELLATION)
    if graph is None:
        return {"error": "policy_missing", "constellation": CONSTELLATION}

    run_id = secrets.token_urlsafe(12)
    memo_stage = {
        "stage": "memo-bind",
        "title_digest": stage_receipt_digest({"title": bundle["title"]}),
        "summary_digest": stage_receipt_digest({"summary": bundle["summary"]}),
        "bound": True,
    }
    memo_digest = stage_receipt_digest(memo_stage)

    request_id = secrets.token_urlsafe(8)
    action_request = ActionRequest(
        request_id=request_id,
        run_id=run_id,
        kind=ACTION_KIND,
        schema=dict(ACTION_SCHEMA),
        audience="decision_maker",
        expires_at=default_action_expires_at(),
        title="Board memo audience and recommendation",
        prompt="Choose the memo audience and your recommendation before PDF seal.",
    )

    record = CheckpointRecord(
        run_id=run_id,
        caller_id=caller_id.strip(),
        constellation=CONSTELLATION,
        disposition="awaiting_input",
        policy_digest=policy_digest_full(CONSTELLATION, graph),
        release=release_identity(graph),
        graph_position="audience-choice",
        stage_receipt_digests=(memo_digest,),
        outstanding_action_requests=(action_request,),
        bundle=bundle,
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
    skill_name: str = "board-memo",
    skill_version: str = "0.1.0",
    key_id: str = "orrery-board-memo-1",
    private_key: Any = None,
) -> dict[str, Any]:
    """Resume a paused board-memo run and seal the PDF composite (idempotent)."""
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

    parsed, parse_error = _parse_response(response)
    if parse_error is not None:
        return parse_error

    if _action_expired(action.expires_at):
        expired = _replace_disposition(record, "expired")
        store.put_checkpoint(expired)
        return checkpoint_status_payload(expired)

    assert parsed is not None

    def _complete() -> dict[str, Any]:
        return _seal_terminal(
            record,
            choice=parsed,
            skill_name=skill_name,
            skill_version=skill_version,
            key_id=key_id,
            private_key=private_key,
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
            graph_position="pdf-seal",
            stage_receipt_digests=tuple(result.get("stage_receipt_digests", ())),
            outstanding_action_requests=(),
            bundle=dict(record.bundle),
            chain=tuple(result.get("chain", ())),
            composite=result,
            artifact_digest=str(result.get("artifact_digest", "")),
            lease_held=False,
            cites=record.cites,
        )
        store.put_checkpoint(completed)
    return result


def cancel(run_id: str, *, caller_id: str = "anonymous") -> dict[str, Any]:
    """Cancel a paused or in-flight board-memo run."""
    return cancel_checkpoint(run_id, caller_id=caller_id)


def _parse_bundle(
    title: object,
    summary: object,
    author: object,
) -> tuple[dict[str, str], dict[str, Any] | None]:
    if not isinstance(title, str) or not title.strip():
        return {}, {"error": "title_required", "status": "inconclusive"}
    if not isinstance(summary, str) or not summary.strip():
        return {}, {"error": "summary_required", "status": "inconclusive"}
    if author is not None and not isinstance(author, str):
        return {}, {"error": "author_invalid", "status": "inconclusive"}
    return {
        "title": title.strip(),
        "summary": summary.strip(),
        "author": (author or "").strip() if isinstance(author, str) else "",
    }, None


def _parse_response(response: object) -> tuple[dict[str, str], dict[str, Any] | None]:
    if not isinstance(response, Mapping):
        return {}, {"error": "response_invalid", "status": "invalid"}
    audience = response.get("audience")
    recommendation = response.get("recommendation")
    if not isinstance(audience, str) or audience not in AUDIENCES:
        return {}, {"error": "audience_invalid", "status": "invalid"}
    if not isinstance(recommendation, str) or recommendation not in RECOMMENDATIONS:
        return {}, {"error": "recommendation_invalid", "status": "invalid"}
    return {"audience": audience, "recommendation": recommendation}, None


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


def _memo_html(bundle: Mapping[str, str], choice: Mapping[str, str]) -> str:
    title = html.escape(bundle["title"])
    summary = html.escape(bundle["summary"])
    author = html.escape(bundle.get("author") or "unknown")
    audience = html.escape(choice["audience"])
    recommendation = html.escape(choice["recommendation"])
    return (
        f"<h1>{title}</h1>"
        f"<p><strong>Author:</strong> {author}</p>"
        f"<p>{summary}</p>"
        f"<p><strong>Audience:</strong> {audience}</p>"
        f"<p><strong>Recommendation:</strong> {recommendation}</p>"
    )


def _seal_terminal(
    record: CheckpointRecord,
    *,
    choice: dict[str, str],
    skill_name: str,
    skill_version: str,
    key_id: str,
    private_key: Any,
) -> dict[str, Any]:
    graph = policy_for(CONSTELLATION)
    if graph is None:
        return {"error": "policy_missing", "constellation": CONSTELLATION}

    pdf_result = html_to_pdf(_memo_html(record.bundle, choice))
    artifact_digest = str(pdf_result["sha256"])
    choice_digest = payload_digest_for(choice)

    choice_stage = {
        "stage": "audience-choice",
        "choice_digest": choice_digest,
        "audience": choice["audience"],
        "recommendation": choice["recommendation"],
    }
    pdf_stage = {
        "stage": "pdf-seal",
        "artifact_digest": artifact_digest,
        "byte_length": pdf_result["byte_length"],
        "page_count": pdf_result["page_count"],
        "content_type": pdf_result["content_type"],
    }
    stage_digests = (
        *record.stage_receipt_digests,
        stage_receipt_digest(choice_stage),
        stage_receipt_digest(pdf_stage),
    )

    bundle_digest = stage_receipt_digest(record.bundle)
    pdf_envelope = sign_envelope(
        payload={
            "gate": "pdf-seal",
            "star_ref": "orrery/html-to-pdf",
            "verdict": "pass",
            "artifact_digest": artifact_digest,
            "page_count": pdf_result["page_count"],
        },
        skill=skill_name,
        version=skill_version,
        tool="continue_run",
        input_digest=bundle_digest,
        private_key=private_key,
        key_id=key_id,
        nonce=f"{record.run_id}-pdf",
    ).to_wire()

    chain = (
        {
            "order": 1,
            "label": "memo-bind",
            "status": "Envelope ✓",
            "note": "title+summary bound",
            "stage_receipt_digest": record.stage_receipt_digests[0],
        },
        {
            "order": 2,
            "label": "audience-choice",
            "status": "Envelope ✓",
            "note": choice_digest,
            "stage_receipt_digest": stage_digests[-2],
        },
        {
            "order": 3,
            "label": "pdf-seal",
            "status": "Envelope ✓",
            "note": artifact_digest,
            "envelope": pdf_envelope,
            "stage_receipt_digest": stage_digests[-1],
        },
    )

    composite: dict[str, Any] = {
        "run_id": record.run_id,
        "constellation": CONSTELLATION,
        "disposition": "completed",
        "chain": "signed-envelope-chain",
        "policy_digest": record.policy_digest,
        "release": dict(record.release),
        "stages": {
            "memo-bind": {"bound": True, "receipt_digest": record.stage_receipt_digests[0]},
            "audience-choice": {
                "audience": choice["audience"],
                "recommendation": choice["recommendation"],
                "choice_digest": choice_digest,
            },
            "pdf-seal": {
                "artifact_digest": artifact_digest,
                "byte_length": pdf_result["byte_length"],
                "page_count": pdf_result["page_count"],
            },
        },
        "stage_receipt_digests": list(stage_digests),
        "artifact_digest": artifact_digest,
        "artifact_base64": pdf_result["artifact_base64"],
        "components": list(_COMPONENTS),
        "limitations": list(_LIMITATIONS),
        "lease_held": False,
        "lease_rule": "waiting_never_holds_worker_lease",
        "chain_steps": list(chain),
    }
    return composite
