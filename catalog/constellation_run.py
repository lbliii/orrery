"""Constellation orchestration — ``run`` / ``status`` / ``continue_run`` (#33).

Checkpointed run state uses ``ConstellationRunStore`` (design #152 / ADR 0007).
Sync demo paths still emit signed Envelope chains in the composite receipt.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from chirp.skill import sign_envelope

from catalog.constellation import PolicyGraph, policy_for
from stars._core.attribution import with_via
from stars._core.migration_profile import canonical_json, sha256_hex
from stars.stale_proof.composite_receipt import (
    normalize_acceptance_cites,
    normalize_cites,
    with_acceptance_cites,
    with_cites,
)

RunStatus = Literal["in_flight", "completed"]
RunDisposition = Literal[
    "queued",
    "running",
    "awaiting_input",
    "awaiting_witness",
    "awaiting_external",
    "completed",
    "failed",
    "cancelled",
    "expired",
]

ReplayKey = tuple[str, str, str, str]


class ConstellationRunError(ValueError):
    """Checkpoint persistence, replay, or resume failed."""


@dataclass(slots=True)
class ActionRequest:
    """Typed pause request (#153)."""

    request_id: str
    run_id: str
    kind: str
    schema: dict[str, Any]
    audience: str
    expires_at: str
    title: str | None = None
    prompt: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "kind": self.kind,
            "schema": self.schema,
            "audience": self.audience,
            "expires_at": self.expires_at,
        }
        if self.title is not None:
            payload["title"] = self.title
        if self.prompt is not None:
            payload["prompt"] = self.prompt
        return payload


@dataclass(slots=True)
class CheckpointRecord:
    """Durable constellation run checkpoint (design #152)."""

    run_id: str
    caller_id: str
    constellation: str
    disposition: RunDisposition
    policy_digest: str
    release: dict[str, str]
    graph_position: str
    stage_receipt_digests: tuple[str, ...]
    outstanding_action_requests: tuple[ActionRequest, ...] = ()
    bundle: dict[str, Any] = field(default_factory=dict)
    chain: tuple[dict[str, Any], ...] = ()
    composite: dict[str, Any] | None = None
    artifact_digest: str | None = None
    lease_held: bool = False
    cites: tuple[str, ...] = ()
    acceptance_cites: tuple[str, ...] = ()


@dataclass(slots=True)
class RunState:
    """Legacy sync constellation execution (completed runs only)."""

    run_id: str
    constellation: str
    status: RunStatus
    bundle: dict[str, Any]
    policy_digest: str
    chain: tuple[dict[str, Any], ...]
    release: dict[str, str]
    cites: tuple[str, ...] = ()
    acceptance_cites: tuple[str, ...] = ()


class ConstellationRunStore:
    """In-memory checkpoint store with idempotent ``continue_run`` replay."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, CheckpointRecord] = {}
        self._sync_runs: dict[str, RunState] = {}
        self._replay: dict[ReplayKey, dict[str, Any]] = {}
        self._latest_run_id: str | None = None

    def put_checkpoint(self, record: CheckpointRecord) -> None:
        self._checkpoints[record.run_id] = record
        self._latest_run_id = record.run_id

    def get_checkpoint(self, run_id: str) -> CheckpointRecord | None:
        return self._checkpoints.get(run_id)

    def put_sync(self, state: RunState) -> None:
        self._sync_runs[state.run_id] = state
        self._latest_run_id = state.run_id

    def get_sync(self, run_id: str) -> RunState | None:
        return self._sync_runs.get(run_id)

    @property
    def latest_run_id(self) -> str | None:
        return self._latest_run_id

    def seal_continuation(
        self,
        *,
        caller_id: str,
        run_id: str,
        request_id: str,
        payload: Mapping[str, Any],
        producer: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Idempotent resume: same replay key returns the same terminal composite."""
        payload_digest = payload_digest_for(payload)
        key: ReplayKey = (caller_id, run_id, request_id, payload_digest)
        existing = self._replay.get(key)
        if existing is not None:
            return {**existing, "replayed": True}

        prefix = (caller_id, run_id, request_id)
        for replay_key, _sealed in self._replay.items():
            if replay_key[:3] == prefix and replay_key[3] != payload_digest:
                raise ConstellationRunError("replay_incompatible")

        result = dict(producer())
        self._replay[key] = result
        return result


_STORE = ConstellationRunStore()


def get_run_store() -> ConstellationRunStore:
    """Return the process-wide constellation run store."""
    return _STORE


def reset_run_store() -> None:
    """Clear all checkpoint and sync run state (tests only)."""
    global _STORE
    _STORE = ConstellationRunStore()


def payload_digest_for(payload: Mapping[str, Any]) -> str:
    """Replay digest for ``continue_run`` (#152)."""
    return sha256_hex(canonical_json(dict(payload)))


def stage_receipt_digest(stage: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json(dict(stage)))


def default_action_expires_at(*, hours: int = 24) -> str:
    return (datetime.now(tz=UTC) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def _input_digest(bundle: dict[str, Any]) -> str:
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _policy_digest(name: str, graph: PolicyGraph) -> str:
    blob = json.dumps(
        {
            "constellation": name,
            "nodes": [n.id for n in graph.nodes],
            "edges": [(e.source, e.target, e.kind) for e in graph.edges],
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()[:16] + "…"


def policy_digest_full(name: str, graph: PolicyGraph) -> str:
    """Full policy digest including release identity (ADR 0007)."""
    blob = json.dumps(
        {
            "constellation": name,
            "nodes": [node.id for node in graph.nodes],
            "edges": [(edge.source, edge.target, edge.kind) for edge in graph.edges],
            "release": {
                "digest": graph.release_digest,
                "key_id": graph.release_key_id,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def release_identity(graph: PolicyGraph) -> dict[str, str]:
    return {"digest": graph.release_digest, "key_id": graph.release_key_id}


def _node_for_label(graph: PolicyGraph, label: str) -> Any:
    key = label.rstrip("*")
    for node in graph.nodes:
        if node.id == key or node.label.rstrip("*") == key:
            return node
    return None


def _sign_gate_envelope(
    *,
    step_label: str,
    star_ref: str | None,
    bundle: dict[str, Any],
    bundle_digest: str,
    run_id: str,
    order: int,
    skill_name: str,
    skill_version: str,
    key_id: str,
    private_key: Any,
) -> dict[str, Any]:
    env = sign_envelope(
        payload={
            "gate": step_label,
            "star_ref": star_ref,
            "verdict": "pass",
            "bundle": {
                "pages": len(bundle.get("pages") or []),
                "links": len(bundle.get("links") or []),
                "examples": len(bundle.get("examples") or []),
            },
            "stub": True,
        },
        skill=skill_name,
        version=skill_version,
        tool="run",
        input_digest=bundle_digest,
        private_key=private_key,
        key_id=key_id,
        nonce=f"{run_id}-{order}",
    )
    return env.to_wire()


def checkpoint_status_payload(record: CheckpointRecord) -> dict[str, Any]:
    """Read-only ``status(run_id)`` wire for checkpointed runs (#153)."""
    payload: dict[str, Any] = {
        "run_id": record.run_id,
        "constellation": record.constellation,
        "disposition": record.disposition,
        "policy_digest": record.policy_digest,
        "release": dict(record.release),
        "graph_position": record.graph_position,
        "stage_receipt_digests": list(record.stage_receipt_digests),
        "outstanding_action_requests": [
            request.as_dict() for request in record.outstanding_action_requests
        ],
        "lease_held": record.lease_held,
        "lease_rule": "waiting_never_holds_worker_lease",
    }
    if record.composite is not None:
        payload["composite"] = dict(record.composite)
    if record.artifact_digest is not None:
        payload["artifact_digest"] = record.artifact_digest
    if record.chain:
        payload["chain"] = list(record.chain)
    if record.cites:
        payload["cites"] = list(record.cites)
    if record.acceptance_cites:
        payload["acceptance_cites"] = list(record.acceptance_cites)
    return payload


def cancel_checkpoint(
    run_id: str,
    *,
    caller_id: str = "anonymous",
) -> dict[str, Any]:
    """Terminal cancel for a checkpointed run (#153)."""
    store = get_run_store()
    record = store.get_checkpoint(run_id)
    if record is None:
        return {"error": "not_found", "run_id": run_id, "status": "not_found"}
    if record.caller_id != caller_id:
        return {"error": "forbidden", "run_id": run_id, "status": "forbidden"}
    if record.disposition in {"completed", "cancelled", "expired", "failed"}:
        return checkpoint_status_payload(record)
    cancelled = CheckpointRecord(
        run_id=record.run_id,
        caller_id=record.caller_id,
        constellation=record.constellation,
        disposition="cancelled",
        policy_digest=record.policy_digest,
        release=dict(record.release),
        graph_position=record.graph_position,
        stage_receipt_digests=record.stage_receipt_digests,
        outstanding_action_requests=(),
        bundle=dict(record.bundle),
        chain=record.chain,
        lease_held=False,
        cites=record.cites,
        acceptance_cites=record.acceptance_cites,
    )
    store.put_checkpoint(cancelled)
    return checkpoint_status_payload(cancelled)


_BOARD_MEMO_CONTINUE_RESPONSE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "audience": {"type": "string", "enum": ["board", "executive", "investor"]},
        "recommendation": {"type": "string", "enum": ["approve", "defer", "revise"]},
    },
    "required": ["audience", "recommendation"],
}

_MIGRATION_DECISIONS_RESPONSE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "feature_id": {"type": "string", "minLength": 1},
                    "action": {"type": "string"},
                },
                "required": ["feature_id", "action"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["decisions"],
    "additionalProperties": False,
}

RESUMABLE_CONTINUE_GUIDES: dict[str, dict[str, Any]] = {
    "orrery/board-memo": {
        "mcp_path": "/constellations/board-memo/mcp",
        "continue_shapes": {
            "audience-choice": {
                "tool": "continue_run",
                "graph_position": "audience-choice",
                "response_schema": _BOARD_MEMO_CONTINUE_RESPONSE,
                "example_response": {"audience": "board", "recommendation": "approve"},
            },
        },
        "mcp_sequence": [
            {
                "step": 1,
                "tool": "run",
                "arguments": {
                    "title": "Q3 Platform Update",
                    "summary": "Revenue grew 12% with stable infra costs.",
                    "author": "ops",
                    "caller_id": "demo-client",
                },
                "expect": {
                    "disposition": "awaiting_input",
                    "graph_position": "audience-choice",
                },
            },
            {
                "step": 2,
                "tool": "continue_run",
                "stage_id": "audience-choice",
                "arguments": {
                    "run_id": "<run_id from step 1>",
                    "request_id": "<outstanding_action_requests[0].request_id>",
                    "response": {"audience": "board", "recommendation": "approve"},
                    "caller_id": "demo-client",
                },
                "expect": {"disposition": "completed", "terminal": "pdf-seal"},
            },
        ],
    },
    "orrery/docs-migrate-to-mdx": {
        "mcp_path": "/constellations/docs-migrate-to-mdx/mcp",
        "continue_shapes": {
            "unsupported-decision": {
                "tool": "continue_run",
                "graph_position": "unsupported-decision",
                "response_schema": {
                    **_MIGRATION_DECISIONS_RESPONSE,
                    "properties": {
                        "decisions": {
                            **_MIGRATION_DECISIONS_RESPONSE["properties"]["decisions"],
                            "items": {
                                **_MIGRATION_DECISIONS_RESPONSE["properties"]["decisions"]["items"],
                                "properties": {
                                    "feature_id": {"type": "string", "minLength": 1},
                                    "action": {"type": "string", "enum": ["hold", "abort"]},
                                },
                            },
                        }
                    },
                },
                "example_response": {
                    "decisions": [
                        {"feature_id": "myst.directive.include", "action": "hold"},
                    ],
                },
            },
        },
        "mcp_sequence": [
            {
                "step": 1,
                "tool": "run",
                "arguments": {
                    "entries": [{"path": "index.md", "content": "..."}],
                    "profile": {"profile_id": "docs-mdx/v1", "source_format": "myst"},
                    "caller_id": "demo-client",
                },
                "expect": {
                    "disposition": "awaiting_input",
                    "graph_position": "unsupported-decision",
                },
            },
            {
                "step": 2,
                "tool": "continue_run",
                "stage_id": "unsupported-decision",
                "arguments": {
                    "run_id": "<run_id from step 1>",
                    "request_id": "<outstanding_action_requests[0].request_id>",
                    "response": {
                        "decisions": [
                            {"feature_id": "myst.directive.include", "action": "hold"},
                        ],
                    },
                    "caller_id": "demo-client",
                },
                "expect": {"disposition": "completed", "terminal": "artifact-seal"},
            },
        ],
    },
    "orrery/api-spec-upgrade": {
        "mcp_path": "/constellations/api-spec-upgrade/mcp",
        "continue_shapes": {
            "breaking-approval": {
                "tool": "continue_run",
                "graph_position": "breaking-approval",
                "response_schema": {
                    **_MIGRATION_DECISIONS_RESPONSE,
                    "properties": {
                        "decisions": {
                            **_MIGRATION_DECISIONS_RESPONSE["properties"]["decisions"],
                            "items": {
                                **_MIGRATION_DECISIONS_RESPONSE["properties"]["decisions"]["items"],
                                "properties": {
                                    "feature_id": {"type": "string", "minLength": 1},
                                    "action": {"type": "string", "enum": ["approve", "abort"]},
                                },
                            },
                        }
                    },
                },
                "example_response": {
                    "decisions": [
                        {"feature_id": "openapi.discriminator", "action": "approve"},
                    ],
                },
            },
        },
        "mcp_sequence": [
            {
                "step": 1,
                "tool": "run",
                "arguments": {
                    "entries": [{"path": "openapi.yaml", "content": "..."}],
                    "profile": {
                        "profile_id": "api-spec/v1",
                        "source_version": "3.0",
                        "target_version": "3.1",
                    },
                    "caller_id": "demo-client",
                },
                "expect": {
                    "disposition": "awaiting_input",
                    "graph_position": "breaking-approval",
                },
            },
            {
                "step": 2,
                "tool": "continue_run",
                "stage_id": "breaking-approval",
                "arguments": {
                    "run_id": "<run_id from step 1>",
                    "request_id": "<outstanding_action_requests[0].request_id>",
                    "response": {
                        "decisions": [
                            {"feature_id": "openapi.discriminator", "action": "approve"},
                        ],
                    },
                    "caller_id": "demo-client",
                },
                "expect": {"disposition": "completed", "terminal": "artifact-seal"},
            },
        ],
    },
}


def continue_guide_for(name: str) -> dict[str, Any] | None:
    """Stage-specific ``continue_run`` shapes and MCP sequence for resumable graphs."""
    guide = RESUMABLE_CONTINUE_GUIDES.get(name)
    return None if guide is None else dict(guide)


def explain_policy(name: str = "acme/launch-gate") -> dict[str, Any]:
    """Plain-language gates, repair loops, and fan-in for a constellation.

    Aligns with Agent Card constellation fields (#220 + ADR 0007):
    ``graph_summary``, input schema, ``dispositions``, ``run_contract``,
    ``member_stars``, and ``subtree_contract``. When invoked through the MCP
    ``explain_policy`` tool, Chirp seals this payload in a signed Envelope.
    """
    from catalog.agent_card import (
        DEFAULT_DISPOSITIONS,
        card_for,
        member_stars_from_policy,
        subtree_contract_from_policy,
    )

    graph = policy_for(name)
    if graph is None:
        return {"error": "not_found", "name": name, "status": "not_found"}

    card = card_for(name)
    gate_nodes = sorted(
        (n for n in graph.nodes if n.node_kind in ("gate", "witness", "pause")),
        key=lambda n: n.step,
    )
    repair = next((e for e in graph.edges if e.kind == "repair_loop"), None)
    fan_in: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.kind == "fan_in":
            fan_in.setdefault(edge.target, []).append(edge.source)

    terminal = next(
        (n.label for n in graph.nodes if n.node_kind == "composite"),
        "release",
    )
    graph_summary = (
        None
        if card is None or card.graph_summary is None
        else card.graph_summary
    )
    if not graph_summary:
        graph_summary = " → ".join(n.label for n in gate_nodes) + f" → {terminal}"

    narrative: list[str] = [
        f"Constellation {name} evaluates {len(gate_nodes)} gates before {terminal}.",
        f"Graph: {graph_summary}.",
        "Gate order: " + " → ".join(n.label for n in gate_nodes) + f" → {terminal}.",
    ]
    if name == "orrery/stale-proof":
        narrative.append(
            "Parable: seal live now + upstream observe/diff "
            "(+ optional PDF receipt); do not install or clone for live truth."
        )
        narrative.append("Step budget: ≤ 3 gates.")
    if name == "orrery/board-memo":
        narrative.append(
            "Resumable demo: memo-bind → audience-choice pause → pdf-seal composite."
        )
        narrative.append("Waiting never holds a worker lease (ADR 0007).")
    if name == "orrery/docs-migrate-to-mdx":
        narrative.append(
            "Frozen migration: inventory → profile pin → safe convert → "
            "optional unsupported-decision pause → validate-diff → artifact-seal."
        )
        narrative.append(
            "Consumes migration star sealed outputs; default receipts omit raw source."
        )
    if name == "orrery/api-spec-upgrade":
        narrative.append(
            "Frozen OpenAPI upgrade: inventory → profile pin → safe upgrade → "
            "optional breaking-approval pause → validate-target → "
            "compatibility-diff → artifact-seal."
        )
        narrative.append(
            "validate-target and compatibility-diff digests remain distinct; "
            "approvals record policy exceptions without rewriting diff evidence."
        )
    if graph.repair_loop_max and repair is not None:
        narrative.append(
            f"Repair loop: {repair.source} may retry {repair.target} "
            f"up to {graph.repair_loop_max} times."
        )
    for target, sources in fan_in.items():
        narrative.append(f"Fan-in: {target} collects evidence from {', '.join(sources)}.")
    narrative.append(
        f"Release composite is signed under {graph.release_key_id} ({graph.release_digest})."
    )

    inputs = [] if card is None else [item.as_dict() for item in card.inputs]
    run_contract = None if card is None or card.run_contract is None else dict(card.run_contract)
    dispositions = (
        list(DEFAULT_DISPOSITIONS)
        if card is None or card.dispositions is None
        else list(card.dispositions)
    )
    members = (
        [dict(item) for item in card.member_stars]
        if card is not None and card.member_stars is not None
        else [dict(item) for item in member_stars_from_policy(name)]
    )
    if card is not None and card.subtree_contract is not None:
        subtree = card.as_dict()["subtree_contract"]
    else:
        subtree = subtree_contract_from_policy(
            name,
            dispositions=tuple(dispositions),
        )

    guide = continue_guide_for(name)
    payload: dict[str, Any] = {
        "constellation": name,
        "status": "ok",
        "graph_summary": graph_summary,
        "inputs": inputs,
        "input_schema": {
            "type": "object",
            "properties": {
                item["name"]: {
                    "type": item.get("type", "string"),
                    **(
                        {"description": item["note"]}
                        if isinstance(item.get("note"), str)
                        else {}
                    ),
                }
                for item in inputs
            },
            "required": [item["name"] for item in inputs if item.get("required")],
        },
        "dispositions": dispositions,
        "run_contract": run_contract,
        "member_stars": members,
        "subtree_contract": subtree,
        "gates": [n.label for n in gate_nodes],
        "repair_loop": {
            "from": repair.source if repair else None,
            "to": repair.target if repair else None,
            "max_retries": graph.repair_loop_max,
        },
        "fan_in": [{"target": t, "sources": s} for t, s in fan_in.items()],
        "release": {
            "digest": graph.release_digest,
            "key_id": graph.release_key_id,
        },
        "narrative": " ".join(narrative),
        "footnote": graph.footnote,
    }
    if guide is not None:
        payload["mcp_path"] = guide["mcp_path"]
        payload["continue_shapes"] = guide["continue_shapes"]
        payload["mcp_sequence"] = guide["mcp_sequence"]
        if run_contract is not None:
            merged = dict(run_contract)
            merged.setdefault("mcp_path", guide["mcp_path"])
            merged.setdefault("continue_shapes", guide["continue_shapes"])
            payload["run_contract"] = merged
    return payload


def run_constellation(
    bundle: dict[str, Any],
    *,
    constellation: str,
    skill_name: str,
    skill_version: str,
    key_id: str,
    private_key: Any,
    cites: list[str] | tuple[str, ...] | None = None,
    acceptance_cites: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Execute a constellation on a Doc Bundle and return the composite chain."""
    graph = policy_for(constellation)
    if graph is None:
        return {
            "error": "not_found",
            "constellation": constellation,
            "status": "not_found",
        }

    run_id = secrets.token_urlsafe(12)
    bundle_digest = _input_digest(bundle)
    policy_d = _policy_digest(constellation, graph)

    chain: list[dict[str, Any]] = []
    for step in graph.composite_chain:
        node = _node_for_label(graph, step.label)
        wire = _sign_gate_envelope(
            step_label=step.label,
            star_ref=node.star_ref if node is not None else None,
            bundle=bundle,
            bundle_digest=bundle_digest,
            run_id=run_id,
            order=step.order,
            skill_name=skill_name,
            skill_version=skill_version,
            key_id=key_id,
            private_key=private_key,
        )
        if step.note.startswith("pay_"):
            wire["payment_id"] = step.note
        chain.append(
            {
                "order": step.order,
                "label": step.label,
                "status": step.status,
                "note": step.note,
                "envelope": wire,
            }
        )

    cite_tuple = normalize_cites(cites)
    acceptance_cite_tuple = normalize_acceptance_cites(acceptance_cites)

    state = RunState(
        run_id=run_id,
        constellation=constellation,
        status="completed",
        bundle=bundle,
        policy_digest=policy_d,
        chain=tuple(chain),
        release={
            "digest": graph.release_digest,
            "key_id": graph.release_key_id,
        },
        cites=cite_tuple,
        acceptance_cites=acceptance_cite_tuple,
    )
    get_run_store().put_sync(state)

    return _composite_receipt_payload(state, chain=list(chain))


def _composite_receipt_payload(
    state: RunState,
    *,
    chain: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": state.run_id,
        "constellation": state.constellation,
        "status": state.status,
        "policy_digest": state.policy_digest,
        "bundle": state.bundle,
        "chain": list(state.chain) if chain is None else chain,
        "release": state.release,
    }
    result = payload
    if state.cites:
        result = with_cites(result, state.cites)
    if state.acceptance_cites:
        result = with_acceptance_cites(result, state.acceptance_cites)
    return with_via(result)


def status_for_run(run_id: str = "") -> dict[str, Any]:
    """Return checkpoint, in-flight, or completed composite receipt for a run."""
    store = get_run_store()
    resolved = run_id.strip() or (store.latest_run_id or "")
    if not resolved:
        return {"error": "not_found", "run_id": run_id, "status": "not_found"}

    checkpoint = store.get_checkpoint(resolved)
    if checkpoint is not None:
        return checkpoint_status_payload(checkpoint)

    state = store.get_sync(resolved)
    if state is None:
        return {"error": "not_found", "run_id": resolved, "status": "not_found"}

    return _composite_receipt_payload(state)
