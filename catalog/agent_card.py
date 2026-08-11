"""Versioned Agent Cards — agent-actionable catalog metadata (#217).

Agent Cards are the single source of truth for *when* to call a star or
constellation, what to pass, and what comes back. They are projected into
resolve, gaze shortlists, gaze_describe, and the published JSON Schema at
``/.well-known/orrery/agent-card.schema.json``.

Progressive disclosure mirrors :class:`ProviderCard`: gaze_match carries a
compact preview (summary, ≤3 use_when bullets, short input summary); resolve
and gaze_describe carry the full card. Gaze never returns live tool bodies.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class AgentCardError(ValueError):
    """An agent card is missing required fields or fails validation."""


@dataclass(frozen=True, slots=True)
class AgentCardIO:
    """One named input or output on an agent card."""

    name: str
    type: str
    required: bool = False
    note: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
        }
        if self.note is not None:
            payload["note"] = self.note
        return payload


#: Sealed composite outcomes agents should expect from constellation runs.
DEFAULT_DISPOSITIONS: tuple[str, ...] = ("ready", "not-ready", "stale", "blocked")
CONTENT_READINESS_DISPOSITIONS: tuple[str, ...] = ("ready", "needs-work", "inconclusive")
AUTHORIZED_CONTENT_PATCH_DISPOSITIONS: tuple[str, ...] = (
    "authorized",
    "denied",
    "needs-work",
    "inconclusive",
)
PUBLISH_GATE_DISPOSITIONS: tuple[str, ...] = (
    "released",
    "denied",
    "awaiting_witness",
    "inconclusive",
)
BOARD_MEMO_DISPOSITIONS: tuple[str, ...] = (
    "completed",
    "awaiting_input",
    "inconclusive",
    "failed",
    "cancelled",
    "expired",
)
DOCS_MIGRATE_TO_MDX_DISPOSITIONS: tuple[str, ...] = BOARD_MEMO_DISPOSITIONS
API_SPEC_UPGRADE_DISPOSITIONS: tuple[str, ...] = BOARD_MEMO_DISPOSITIONS

#: ADR 0007 lease invariant — paused runs never hold a worker/MCP lease.
LEASE_RULE = "waiting_never_holds_worker_lease"

#: ADR 0007 stage roles (planner freeze vocabulary).
_STAGE_ROLES = frozenset({"gate", "witness", "fan_in", "composite", "pause"})

#: Optional planner-shelf hints (#246) — informational only; agent ranks.
TREE_ROLES = frozenset({"worker", "planner", "review"})
WORKER_COSTS = frozenset({"low", "mid", "high"})


@dataclass(frozen=True, slots=True)
class AgentCard:
    """Versioned, policy-first metadata for one resolvable name."""

    summary: str
    use_when: tuple[str, ...]
    not_for: tuple[str, ...]
    example_intents: tuple[str, ...]
    locality: str
    write_authority: str
    approval: str
    inputs: tuple[AgentCardIO, ...]
    outputs: tuple[AgentCardIO, ...]
    tools: tuple[str, ...]
    coverage_href: str
    agent_card_version: str = "1.0"
    run_contract: Mapping[str, object] | None = None
    graph_summary: str | None = None
    dispositions: tuple[str, ...] | None = None
    member_stars: tuple[Mapping[str, object], ...] | None = None
    subtree_contract: Mapping[str, object] | None = None
    tree_role: str | None = None
    worker_cost: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Full card for resolve / gaze_describe (no live tool payloads)."""
        payload: dict[str, object] = {
            "agent_card_version": self.agent_card_version,
            "summary": self.summary,
            "use_when": list(self.use_when),
            "not_for": list(self.not_for),
            "example_intents": list(self.example_intents),
            "locality": self.locality,
            "write_authority": self.write_authority,
            "approval": self.approval,
            "inputs": [item.as_dict() for item in self.inputs],
            "outputs": [item.as_dict() for item in self.outputs],
            "tools": list(self.tools),
            "coverage_href": self.coverage_href,
        }
        if self.run_contract is not None:
            payload["run_contract"] = dict(self.run_contract)
        if self.graph_summary is not None:
            payload["graph_summary"] = self.graph_summary
        if self.dispositions is not None:
            payload["dispositions"] = list(self.dispositions)
        if self.member_stars is not None:
            payload["member_stars"] = [dict(item) for item in self.member_stars]
        if self.subtree_contract is not None:
            payload["subtree_contract"] = _copy_subtree_contract(self.subtree_contract)
        if self.tree_role is not None:
            payload["tree_role"] = self.tree_role
        if self.worker_cost is not None:
            payload["worker_cost"] = self.worker_cost
        return payload

    def gaze_preview(self) -> dict[str, object]:
        """Compact progressive-disclosure fields for gaze_match hits."""
        preview: dict[str, object] = {
            "summary": self.summary,
            "use_when": list(self.use_when[:3]),
            "inputs_summary": inputs_summary(self),
        }
        if self.tree_role is not None:
            preview["tree_role"] = self.tree_role
        if self.worker_cost is not None:
            preview["worker_cost"] = self.worker_cost
        return preview

    def searchable_text(self) -> str:
        """Concatenated text indexed by gaze match/search."""
        parts = [self.summary, *self.use_when, *self.example_intents]
        return " ".join(parts).lower()


def inputs_summary(card: AgentCard) -> str:
    """Short human/agent-facing input blurb for gaze shortlists.

    Prefer ``run_contract.required_inputs`` / ``optional_inputs`` when present
    so constellation hits advertise what ``run`` expects (#220).
    """
    if card.run_contract is not None:
        required = [str(name) for name in (card.run_contract.get("required_inputs") or [])]
        optional = [str(name) for name in (card.run_contract.get("optional_inputs") or [])]
        bits = [f"{name}*" for name in required]
        bits.extend(optional)
        return ", ".join(bits) if bits else "no required inputs"
    if not card.inputs:
        return "no inputs"
    bits: list[str] = []
    for item in card.inputs:
        label = item.name
        if item.required:
            label = f"{label}*"
        bits.append(label)
    return ", ".join(bits)


def _io(
    name: str,
    type_: str,
    *,
    required: bool = False,
    note: str | None = None,
) -> AgentCardIO:
    return AgentCardIO(name=name, type=type_, required=required, note=note)


def member_stars_from_policy(name: str) -> tuple[dict[str, object], ...]:
    """Derive member-star roles from the constellation policy graph."""
    from .constellation import policy_for

    graph = policy_for(name)
    if graph is None:
        return ()
    members: list[dict[str, object]] = []
    for node in graph.nodes:
        if node.node_kind == "composite":
            continue
        members.append(
            {
                "name": node.star_ref or node.id,
                "role": node.node_kind,
                "label": node.label,
            }
        )
    return tuple(members)


def _copy_subtree_contract(contract: Mapping[str, object]) -> dict[str, object]:
    """Deep-ish copy suitable for agent-card / explain_policy wire payloads."""
    stages = contract.get("stages") or []
    pause = contract.get("pause_policy") or {}
    receipt = contract.get("composite_receipt_fields") or {}
    release = receipt.get("release") if isinstance(receipt, Mapping) else None
    return {
        "stages": [dict(stage) for stage in stages],  # type: ignore[arg-type]
        "pause_policy": dict(pause),  # type: ignore[arg-type]
        "composite_receipt_fields": {
            **dict(receipt),  # type: ignore[arg-type]
            **(
                {"release": dict(release)}  # type: ignore[arg-type]
                if isinstance(release, Mapping)
                else {}
            ),
        },
        "lease_rule": contract["lease_rule"],
    }


def _policy_digest_for_contract(name: str, graph: Any) -> str:
    """Digest of stages + edges + release identity (ADR 0007)."""
    import hashlib
    import json

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


def subtree_contract_from_policy(
    name: str,
    *,
    dispositions: tuple[str, ...] | None = None,
    pause_allowed: bool = False,
    pause_modes: tuple[str, ...] | None = None,
    continuation_tools: tuple[str, ...] | None = None,
    release_digest: str | None = None,
    release_key_id: str | None = None,
    policy_digest: str | None = None,
    stages: tuple[Mapping[str, object], ...] | None = None,
) -> dict[str, object]:
    """Build ADR 0007 ``subtree_contract`` for a constellation card.

    Existing public graphs are synchronous-only (``pause_policy.allowed`` false)
    unless a stage is already a durable pause.
    """
    from .constellation import policy_for

    graph = policy_for(name)
    disposition_values = dispositions if dispositions is not None else DEFAULT_DISPOSITIONS

    if stages is None:
        if graph is None:
            raise AgentCardError(f"no policy graph for subtree_contract: {name!r}")
        built_stages: list[dict[str, object]] = []
        for node in sorted(graph.nodes, key=lambda item: item.step):
            role = node.node_kind if node.node_kind in _STAGE_ROLES else "gate"
            stage: dict[str, object] = {
                "id": node.id,
                "label": node.label,
                "role": role,
            }
            if node.star_ref:
                stage["star_ref"] = node.star_ref
            built_stages.append(stage)
    else:
        built_stages = [dict(stage) for stage in stages]

    pause_policy: dict[str, object] = {
        "allowed": pause_allowed,
        "checkpoint_after_each_stage": True,
    }
    if pause_allowed:
        pause_policy["modes"] = list(pause_modes or ())
        pause_policy["continuation_tools"] = list(continuation_tools or ())

    digest = release_digest
    key_id = release_key_id
    frozen_digest = policy_digest
    if graph is not None:
        if digest is None:
            digest = graph.release_digest
        if key_id is None:
            key_id = graph.release_key_id
        if frozen_digest is None:
            frozen_digest = _policy_digest_for_contract(name, graph)
    if not digest or not key_id or not frozen_digest:
        raise AgentCardError(f"subtree_contract needs release identity for {name!r}")

    return {
        "stages": built_stages,
        "pause_policy": pause_policy,
        "composite_receipt_fields": {
            "chain": "signed-envelope-chain",
            "disposition": list(disposition_values),
            "policy_digest": frozen_digest,
            "release": {"digest": digest, "key_id": key_id},
        },
        "lease_rule": LEASE_RULE,
    }


def _card(
    *,
    summary: str,
    use_when: tuple[str, ...],
    not_for: tuple[str, ...],
    example_intents: tuple[str, ...],
    tools: tuple[str, ...],
    coverage_slug: str,
    inputs: tuple[AgentCardIO, ...] = (),
    outputs: tuple[AgentCardIO, ...] = (),
    locality: str = "orrery-hosted",
    write_authority: str = "read-only",
    approval: str = "not-required",
    run_contract: Mapping[str, object] | None = None,
    graph_summary: str | None = None,
    dispositions: tuple[str, ...] | None = None,
    member_stars: tuple[Mapping[str, object], ...] | None = None,
    subtree_contract: Mapping[str, object] | None = None,
    tree_role: str | None = None,
    worker_cost: str | None = None,
) -> AgentCard:
    return AgentCard(
        summary=summary,
        use_when=use_when,
        not_for=not_for,
        example_intents=example_intents,
        locality=locality,
        write_authority=write_authority,
        approval=approval,
        inputs=inputs,
        outputs=outputs,
        tools=tools,
        coverage_href=f"/coverage/{coverage_slug}",
        run_contract=run_contract,
        graph_summary=graph_summary,
        dispositions=dispositions,
        member_stars=member_stars,
        subtree_contract=subtree_contract,
        tree_role=tree_role,
        worker_cost=worker_cost,
    )


#: Signed envelope output shared by most public stars.
_ENVELOPE = (_io("envelope", "signed-envelope"),)
_CONTENT = (_io("content", "string"), *_ENVELOPE)


def validate_agent_card(card: AgentCard, *, name: str | None = None) -> None:
    """Reject incomplete or malformed agent cards (CI / sync guard)."""
    where = f" for {name}" if name else ""
    if not card.agent_card_version.strip():
        raise AgentCardError(f"agent_card_version must be non-empty{where}")
    if not card.summary.strip():
        raise AgentCardError(f"summary must be non-empty{where}")
    if not card.use_when:
        raise AgentCardError(f"use_when must list at least one bullet{where}")
    if any(not bullet.strip() for bullet in card.use_when):
        raise AgentCardError(f"use_when bullets must be non-empty{where}")
    if not card.not_for:
        raise AgentCardError(f"not_for must list at least one boundary{where}")
    if not card.example_intents:
        raise AgentCardError(f"example_intents must list at least one intent{where}")
    if not card.locality.strip():
        raise AgentCardError(f"locality must be non-empty{where}")
    if not card.write_authority.strip():
        raise AgentCardError(f"write_authority must be non-empty{where}")
    if not card.approval.strip():
        raise AgentCardError(f"approval must be non-empty{where}")
    if not card.tools:
        raise AgentCardError(f"tools must list at least one tool{where}")
    if not card.coverage_href.startswith("/coverage/"):
        raise AgentCardError(f"coverage_href must start with /coverage/{where}")
    for item in (*card.inputs, *card.outputs):
        if not item.name.strip() or not item.type.strip():
            raise AgentCardError(f"inputs/outputs need name and type{where}")
    if card.run_contract is not None:
        _validate_subtree_contract(card.subtree_contract, where=where)
    if card.tree_role is not None and card.tree_role not in TREE_ROLES:
        raise AgentCardError(
            f"tree_role must be one of {sorted(TREE_ROLES)}{where}"
        )
    if card.worker_cost is not None and card.worker_cost not in WORKER_COSTS:
        raise AgentCardError(
            f"worker_cost must be one of {sorted(WORKER_COSTS)}{where}"
        )


def _validate_subtree_contract(
    contract: Mapping[str, object] | None,
    *,
    where: str,
) -> None:
    """Require ADR 0007 keys on constellation cards (those with run_contract)."""
    if contract is None:
        raise AgentCardError(f"subtree_contract required for constellation cards{where}")
    for key in ("stages", "pause_policy", "composite_receipt_fields", "lease_rule"):
        if key not in contract:
            raise AgentCardError(f"subtree_contract missing {key}{where}")
    if contract.get("lease_rule") != LEASE_RULE:
        raise AgentCardError(
            f"subtree_contract.lease_rule must be {LEASE_RULE!r}{where}"
        )
    pause = contract.get("pause_policy")
    if not isinstance(pause, Mapping) or "allowed" not in pause:
        raise AgentCardError(f"subtree_contract.pause_policy.allowed required{where}")
    if "checkpoint_after_each_stage" not in pause:
        raise AgentCardError(
            f"subtree_contract.pause_policy.checkpoint_after_each_stage required{where}"
        )
    stages = contract.get("stages")
    if not isinstance(stages, list) or not stages:
        raise AgentCardError(f"subtree_contract.stages must be a non-empty list{where}")
    for stage in stages:
        if not isinstance(stage, Mapping):
            raise AgentCardError(f"subtree_contract.stages entries must be objects{where}")
        for key in ("id", "label", "role"):
            if key not in stage:
                raise AgentCardError(f"subtree_contract.stages[].{key} required{where}")
        if stage.get("role") not in _STAGE_ROLES:
            raise AgentCardError(
                f"subtree_contract.stages[].role must be one of {sorted(_STAGE_ROLES)}{where}"
            )
    receipt = contract.get("composite_receipt_fields")
    if not isinstance(receipt, Mapping):
        raise AgentCardError(
            f"subtree_contract.composite_receipt_fields must be an object{where}"
        )
    for key in ("chain", "disposition", "policy_digest", "release"):
        if key not in receipt:
            raise AgentCardError(
                f"subtree_contract.composite_receipt_fields.{key} required{where}"
            )
    if receipt.get("chain") != "signed-envelope-chain":
        raise AgentCardError(
            f"subtree_contract.composite_receipt_fields.chain must be "
            f"'signed-envelope-chain'{where}"
        )
    release = receipt.get("release")
    if not isinstance(release, Mapping) or "digest" not in release or "key_id" not in release:
        raise AgentCardError(
            f"subtree_contract.composite_receipt_fields.release needs digest+key_id{where}"
        )


def agent_card_json_schema() -> dict[str, Any]:
    """JSON Schema (draft 2020-12) for Agent Card v1."""
    io_schema = {
        "type": "object",
        "required": ["name", "type"],
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "type": {"type": "string", "minLength": 1},
            "required": {"type": "boolean"},
            "note": {"type": "string"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://orrery.lol/.well-known/orrery/agent-card.schema.json",
        "title": "Orrery Agent Card",
        "description": (
            "Agent-actionable metadata for a public star or constellation. "
            "Informational shortlist data — the agent remains the semantic router."
        ),
        "type": "object",
        "required": [
            "agent_card_version",
            "summary",
            "use_when",
            "not_for",
            "example_intents",
            "locality",
            "write_authority",
            "approval",
            "inputs",
            "outputs",
            "tools",
            "coverage_href",
        ],
        "additionalProperties": False,
        "properties": {
            "agent_card_version": {"type": "string", "const": "1.0"},
            "summary": {"type": "string", "minLength": 1},
            "use_when": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "not_for": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "example_intents": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "locality": {"type": "string", "minLength": 1},
            "write_authority": {"type": "string", "minLength": 1},
            "approval": {"type": "string", "minLength": 1},
            "inputs": {"type": "array", "items": io_schema},
            "outputs": {"type": "array", "items": io_schema},
            "tools": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "coverage_href": {
                "type": "string",
                "pattern": "^/coverage/",
            },
            "run_contract": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "entry_tool": {"type": "string"},
                    "required_inputs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "optional_inputs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "composite_output": {"type": "string"},
                    "input_bundle": {"type": "object"},
                },
            },
            "graph_summary": {"type": "string"},
            "dispositions": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
            "member_stars": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "role"],
                    "additionalProperties": True,
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "label": {"type": "string"},
                    },
                },
            },
            "tree_role": {
                "type": "string",
                "enum": ["worker", "planner", "review"],
            },
            "worker_cost": {
                "type": "string",
                "enum": ["low", "mid", "high"],
            },
            "subtree_contract": {
                "type": "object",
                "required": [
                    "stages",
                    "pause_policy",
                    "composite_receipt_fields",
                    "lease_rule",
                ],
                "additionalProperties": False,
                "properties": {
                    "stages": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["id", "label", "role"],
                            "additionalProperties": True,
                            "properties": {
                                "id": {"type": "string", "minLength": 1},
                                "label": {"type": "string", "minLength": 1},
                                "role": {
                                    "type": "string",
                                    "enum": [
                                        "gate",
                                        "witness",
                                        "fan_in",
                                        "composite",
                                        "pause",
                                    ],
                                },
                                "star_ref": {"type": "string"},
                                "optional": {"type": "boolean"},
                            },
                        },
                    },
                    "pause_policy": {
                        "type": "object",
                        "required": ["allowed", "checkpoint_after_each_stage"],
                        "additionalProperties": True,
                        "properties": {
                            "allowed": {"type": "boolean"},
                            "modes": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "continuation_tools": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "checkpoint_after_each_stage": {"type": "boolean"},
                        },
                    },
                    "composite_receipt_fields": {
                        "type": "object",
                        "required": [
                            "chain",
                            "disposition",
                            "policy_digest",
                            "release",
                        ],
                        "additionalProperties": True,
                        "properties": {
                            "chain": {
                                "type": "string",
                                "const": "signed-envelope-chain",
                            },
                            "disposition": {},
                            "policy_digest": {"type": "string"},
                            "cites": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "release": {
                                "type": "object",
                                "required": ["digest", "key_id"],
                                "properties": {
                                    "digest": {"type": "string"},
                                    "key_id": {"type": "string"},
                                },
                            },
                        },
                    },
                    "lease_rule": {
                        "type": "string",
                        "const": "waiting_never_holds_worker_lease",
                    },
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Registry — parallel to star.toml; do not mass-rewrite package blurbs (#218)
# ---------------------------------------------------------------------------


_STAR_CARDS: dict[str, AgentCard] = {
    "orrery/gh-file-at-ref": _card(
        summary="Fetch a public repo file pinned to an exact commit SHA.",
        use_when=(
            "You need file contents at a specific revision for review or diffing",
            "You are building evidence that must not drift from a pinned commit",
            "You want a bounded allowlisted GitHub file, not arbitrary paths",
        ),
        not_for=(
            "Private repositories",
            "Repos outside the published allowlist",
            "Branch or tag refs that are not a full 40-char commit SHA",
        ),
        example_intents=(
            "get README at commit",
            "fetch changelog at sha",
            "pinned file from github",
        ),
        tools=("get",),
        coverage_slug="gh-file-at-ref",
        inputs=(
            _io("target", "string", required=True, note="allowlisted named file target"),
            _io("ref", "string", required=True, note="full 40-char commit SHA"),
        ),
        outputs=_CONTENT,
    ),
    "orrery/world-time": _card(
        summary="Live UTC truth at call time; offline clones are stale.",
        use_when=(
            "You need a fresh UTC timestamp sealed in an Envelope",
            "You are proving that a clone cannot mint live clock evidence",
            "You want a liveness witness for a larger policy graph",
        ),
        not_for=(
            "Historical time lookups",
            "Non-UTC local wall clocks",
            "Cached or offline clock packages",
        ),
        example_intents=("live utc now", "current time sealed", "fresh clock evidence"),
        tools=("fetch", "get", "answer"),
        coverage_slug="world-time",
        outputs=(
            _io("dateTime", "string", note="UTC datetime from the live clock"),
            *_ENVELOPE,
        ),
    ),
    "orrery/source-watch": _card(
        summary="Live official-source evidence, digest comparison, and bounded answers.",
        use_when=(
            "You need a fresh digest of an allowlisted official source",
            "You want to compare current content to a prior digest",
            "You need a bounded extractive answer with live source evidence",
        ),
        not_for=(
            "Arbitrary URLs outside the allowlist",
            "Open-ended web search",
            "Mutating remote sources",
        ),
        example_intents=(
            "observe python release notes",
            "diff official source digest",
            "answer from live source",
        ),
        tools=("observe", "diff", "answer"),
        coverage_slug="source-watch",
        inputs=(
            _io("source", "string", note="allowlisted source id"),
            _io("since_digest", "string", note="prior digest for diff"),
            _io("question", "string", note="required for answer"),
        ),
        outputs=(
            _io("digest", "string"),
            _io("changed", "boolean"),
            _io("answer", "string"),
            *_ENVELOPE,
        ),
    ),
    "orrery/html-to-pdf": _card(
        summary="Render simple HTML to a downloadable PDF with signed receipts.",
        use_when=(
            "You need a short-lived PDF artifact from trusted HTML",
            "You want a signed convert receipt for document evidence",
            "You are queueing a managed PDF run and polling for the result",
        ),
        not_for=(
            "Untrusted HTML with active content",
            "Complex CSS/layout engines",
            "Long-term PDF hosting",
        ),
        example_intents=("html to pdf", "render receipt pdf", "convert html document"),
        tools=("convert", "submit", "result", "health"),
        coverage_slug="html-to-pdf",
        inputs=(
            _io("html", "string", required=True),
            _io("idempotency_key", "string", note="required for submit"),
            _io("run_id", "string", note="required for result"),
        ),
        outputs=(
            _io("artifact", "pdf-url"),
            _io("run_id", "string"),
            *_ENVELOPE,
        ),
    ),
    "orrery/http-head": _card(
        summary="Fresh HTTP metadata for named allowlisted official targets.",
        use_when=(
            "You need status/headers for an allowlisted official URL",
            "You are checking freshness without downloading a body",
        ),
        not_for=("Arbitrary URLs", "POST or mutating requests", "Full body retrieval"),
        example_intents=("http head python docs", "fresh headers for target"),
        tools=("head",),
        coverage_slug="http-head",
        inputs=(_io("target", "string", note="allowlisted named target"),),
        outputs=(_io("status", "integer"), _io("headers", "object"), *_ENVELOPE),
    ),
    "orrery/well-known": _card(
        summary="Bounded fresh slices of named official discovery documents.",
        use_when=(
            "You need a slice of an allowlisted well-known document",
            "You are checking discovery metadata without fetching the whole file",
        ),
        not_for=("Private discovery docs", "Arbitrary paths", "Write/update of discovery files"),
        example_intents=("read well-known document", "fresh discovery slice"),
        tools=("read",),
        coverage_slug="well-known",
        inputs=(_io("document", "string", note="allowlisted document id"),),
        outputs=_CONTENT,
    ),
    "orrery/cert-expiry": _card(
        summary="TLS certificate expiry metadata for named allowlisted hosts.",
        use_when=(
            "You need notAfter / SANs for an allowlisted HTTPS host",
            "You are assembling expiry evidence before a renew decision",
        ),
        not_for=("Hosts outside the allowlist", "Certificate issuance", "Private PKI endpoints"),
        example_intents=("cert expiry for host", "tls notAfter inspect"),
        tools=("inspect",),
        coverage_slug="cert-expiry",
        inputs=(_io("host", "string", note="allowlisted HTTPS host"),),
        outputs=(
            _io("not_after", "string"),
            _io("subject", "string"),
            *_ENVELOPE,
        ),
    ),
    "orrery/rfc-section": _card(
        summary="Bounded sections from named allowlisted RFC Editor documents.",
        use_when=(
            "You need a named RFC section, not the whole document",
            "You want bounded normative text for reasoning",
        ),
        not_for=("RFCs outside the allowlist", "Full-document dumps", "Editing RFCs"),
        example_intents=("rfc section text", "get allowlisted rfc clause"),
        tools=("get",),
        coverage_slug="rfc-section",
        inputs=(
            _io("rfc", "string", required=True),
            _io("section", "string", required=True),
        ),
        outputs=_CONTENT,
    ),
    "orrery/pep-section": _card(
        summary="Bounded sections from named canonical Python PEP documents.",
        use_when=(
            "You need a named PEP section for language/runtime guidance",
            "You want bounded PEP text rather than a full download",
        ),
        not_for=("PEPs outside the allowlist", "Full PEP dumps", "Editing PEPs"),
        example_intents=("pep section text", "get python pep clause"),
        tools=("get",),
        coverage_slug="pep-section",
        inputs=(
            _io("pep", "string", required=True),
            _io("section", "string", required=True),
        ),
        outputs=_CONTENT,
    ),
    "orrery/spdx-license": _card(
        summary="Bounded SPDX license text and metadata for named allowlisted identifiers.",
        use_when=(
            "You need SPDX license text for an allowlisted identifier",
            "You are assembling license evidence for a gate",
        ),
        not_for=("Unknown SPDX IDs", "Custom license drafting", "License approval decisions"),
        example_intents=("spdx license text", "get mit license metadata"),
        tools=("get",),
        coverage_slug="spdx-license",
        inputs=(_io("license_id", "string", required=True),),
        outputs=(_io("license_text", "string"), _io("metadata", "object"), *_ENVELOPE),
    ),
    "orrery/csv-url": _card(
        summary="Bounded typed rows from named allowlisted public CSV datasets.",
        use_when=(
            "You need a fresh sample of an allowlisted public CSV",
            "You want typed rows without scraping arbitrary URLs",
        ),
        not_for=("Arbitrary CSV URLs", "Unbounded downloads", "Mutating datasets"),
        example_intents=("get flights csv sample", "fresh allowlisted csv rows"),
        tools=("get",),
        coverage_slug="csv-url",
        inputs=(_io("dataset", "string", required=True),),
        outputs=(_io("rows", "array"), *_ENVELOPE),
    ),
    "orrery/row-lookup": _card(
        summary="Exact typed row lookup in a named allowlisted public CSV dataset.",
        use_when=(
            "You need one exact row by key from an allowlisted dataset",
            "You want typed lookup evidence without scanning the whole file",
        ),
        not_for=("Fuzzy search", "Datasets outside the allowlist", "Bulk exports"),
        example_intents=("lookup flight row", "exact csv key lookup"),
        tools=("lookup",),
        coverage_slug="row-lookup",
        inputs=(
            _io("dataset", "string", required=True),
            _io("key", "object", required=True, note="origin/destination fields"),
        ),
        outputs=(_io("row", "object"), *_ENVELOPE),
    ),
    "orrery/decision-bind": _card(
        summary="Seal a planner decision into a citeable DecisionReceipt with a stable digest.",
        use_when=(
            "You need a citeable freeze before downstream work proceeds",
            "You want offline-verifiable decision_digest evidence, not debate hosting",
        ),
        not_for=(
            "Hosting ADRs or design docs",
            "Multi-party voting or quorum signatures",
            "Fetching statement text by digest alone",
        ),
        example_intents=("seal planner decision", "bind decision receipt"),
        tools=("bind",),
        coverage_slug="decision-bind",
        inputs=(
            _io("decision_id", "string", required=True, note="stable caller id ≤128 chars"),
            _io("statement", "string", required=True, note="exact decision text ≤16 KiB UTF-8"),
            _io("adr_url", "string", note="optional HTTPS ADR link"),
            _io("issue_url", "string", note="optional HTTPS tracker link"),
        ),
        outputs=(
            _io("decision_digest", "string"),
            _io("decided_at", "string"),
            _io("statement", "string"),
            *_ENVELOPE,
        ),
    ),
    "orrery/manifest-bind": _card(
        summary="Bind caller-supplied file digests into a stable manifest_digest receipt.",
        use_when=(
            "You have path/sha256/size rows and need a sealed manifest digest",
            "You want admitted/excluded counts without Orrery opening a repo",
        ),
        not_for=(
            "Reading the caller's repository from disk",
            "Mutating or writing files",
            "Policy evaluation (use manifest-preflight)",
        ),
        example_intents=("bind file manifest digest", "seal caller file inventory"),
        tools=("bind",),
        coverage_slug="manifest-bind",
        inputs=(_io("files", "array", required=True, note="[{path, sha256, size}]"),),
        outputs=(
            _io("manifest_digest", "string"),
            _io("admitted_count", "integer"),
            _io("excluded_count", "integer"),
            *_ENVELOPE,
        ),
    ),
    "orrery/manifest-preflight": _card(
        summary="Preflight a caller file manifest against a named versioned policy.",
        use_when=(
            "You need to check files before run against a named policy",
            "You want pass/fail plus violation codes with no egress",
        ),
        not_for=(
            "Inventing new policy names at call time",
            "Writing files or applying patches",
            "Hosting the caller's repository",
        ),
        example_intents=(
            "check files before run",
            "docs-only preflight",
            "max files policy check",
        ),
        tools=("check",),
        coverage_slug="manifest-preflight",
        inputs=(
            _io("files", "array", required=True),
            _io(
                "policy",
                "string",
                required=True,
                note="orrery/docs-only@v1 or orrery/max-100-files@v1",
            ),
            _io("manifest_digest", "string", note="optional digest claim"),
        ),
        outputs=(
            _io("passed", "boolean"),
            _io("violation_codes", "array"),
            *_ENVELOPE,
        ),
    ),
    "orrery/patch-capture": _card(
        summary="Capture a sealed patch digest from before/after caller file snapshots.",
        use_when=(
            "You need to capture patch receipt evidence for a tree node",
            "You have before/after manifests and want changed paths plus line stats",
        ),
        not_for=(
            "Applying patches or writing files",
            "Hosting unified diffs as a product surface",
            "Unbounded repository walks",
        ),
        example_intents=(
            "capture patch receipt",
            "seal before after file diff",
            "patch digest for changed paths",
        ),
        tools=("capture",),
        coverage_slug="patch-capture",
        inputs=(
            _io("before", "object", required=True, note="snapshot with files[]"),
            _io("after", "object", required=True, note="snapshot with files[]"),
        ),
        outputs=(
            _io("patch_digest", "string"),
            _io("changed_paths", "array"),
            _io("line_stats", "object"),
            *_ENVELOPE,
        ),
    ),
    "orrery/write-authority-check": _card(
        summary="Verify an explicit write grant covers the intended path set.",
        use_when=(
            "You need authorized/denied codes before applying a write",
            "You have a grant_digest and optional signed witness envelope",
        ),
        not_for=(
            "Writing files or applying patches",
            "Multi-party witness ceremonies",
            "Inventing policy names outside explicit-paths@v1",
        ),
        example_intents=(
            "check write authority",
            "verify write grant paths",
            "authorize docs write grant",
        ),
        tools=("check",),
        coverage_slug="write-authority-check",
        inputs=(
            _io("manifest_digest", "string", required=True, note="opaque hex digest"),
            _io(
                "authority",
                "object",
                required=True,
                note="policy, allowed_paths, grant_digest, optional witness",
            ),
        ),
        outputs=(
            _io("authorized", "boolean"),
            _io("codes", "array"),
            _io("grant_digest", "string"),
            *_ENVELOPE,
        ),
    ),
    "orrery/link-check-bounded": _card(
        summary="Bounded allowlisted HTTPS link reachability over markdown/html bundles.",
        use_when=(
            "You need per-link status with an explicit max_link_count cap",
            "You want allowlisted HTTPS HEAD probes over a doc bundle, not a general fetcher",
        ),
        not_for=(
            "Unbounded crawl or arbitrary URL fetch",
            "Named-target HTTP HEAD (use http-head)",
            "Mutating documents",
            "Ship-check / release evidence bundles (use ship-check or stale-proof)",
        ),
        example_intents=(
            "bounded markdown link status",
            "docs links under max_link_count",
            "allowlisted html link reachability",
            "fail loud over link cap",
            "link status for markdown bundle",
        ),
        tools=("check",),
        coverage_slug="link-check-bounded",
        inputs=(
            _io("files", "array", required=True, note="[{path, content, format?}]"),
            _io("max_link_count", "integer", required=True, note="1..50; fail loud over cap"),
        ),
        outputs=(
            _io("links", "array"),
            _io("link_count", "integer"),
            _io("passed", "boolean"),
            *_ENVELOPE,
        ),
    ),
    "orrery/structure-audit": _card(
        summary="Pure markdown structure audit with coded findings.",
        use_when=(
            "You need heading gap / frontmatter / orphan findings on a markdown set",
            "You want a pure sealed audit with no egress",
        ),
        not_for=(
            "MyST inventory analyze-stage digests (use docs-myst-inventory)",
            "Fetching docs from the network",
            "Rewriting or fixing documents",
        ),
        example_intents=(
            "audit markdown structure",
            "find heading level skips",
            "check frontmatter title errors",
            "detect orphan markdown pages",
            "structure findings for docs set",
        ),
        tools=("audit",),
        coverage_slug="structure-audit",
        inputs=(_io("files", "array", required=True, note="[{path, content}] markdown only"),),
        outputs=(
            _io("findings", "array"),
            _io("finding_codes", "array"),
            _io("passed", "boolean"),
            *_ENVELOPE,
        ),
    ),
    "orrery/row-validate": _card(
        summary="Pure validation of one row against a named static source-aligned profile.",
        use_when=(
            "You need to validate a small row against a known profile",
            "You want schema errors without network I/O",
        ),
        not_for=("Profiles outside the allowlist", "Large batch validation", "Data mutation"),
        example_intents=("validate flight row", "check row against profile"),
        tools=("validate",),
        coverage_slug="row-validate",
        inputs=(
            _io("profile", "string", required=True),
            _io("row", "object", required=True),
        ),
        outputs=(_io("ok", "boolean"), _io("errors", "array"), *_ENVELOPE),
    ),
    "orrery/table-diff": _card(
        summary="Pure bounded comparison of two caller-provided tabular snapshots.",
        use_when=(
            "You have two small snapshots and need a keyed diff",
            "You want a deterministic table verdict without fetching data",
        ),
        not_for=("Huge tables", "Fuzzy matching", "Live dataset fetches"),
        example_intents=("diff two table snapshots", "compare keyed rows"),
        tools=("diff",),
        coverage_slug="table-diff",
        inputs=(
            _io("left", "object", required=True),
            _io("right", "object", required=True),
            _io("key_column", "string", required=True),
        ),
        outputs=(_io("verdict", "object"), *_ENVELOPE),
    ),
    "orrery/table-fresh": _card(
        summary="Fresh bounded flights sample and deterministic table-diff verdict.",
        use_when=(
            "You need live CSV sample evidence compared to a baseline",
            "You want a freshness verdict sealed for a policy step",
        ),
        not_for=("Arbitrary datasets", "Unbounded samples", "Deploy approval"),
        example_intents=("freshen flights sample", "table freshness verdict"),
        tools=("run",),
        coverage_slug="table-fresh",
        inputs=(_io("baseline", "object", required=True),),
        outputs=(_io("verdict", "object"), *_ENVELOPE),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["baseline"],
            "optional_inputs": [],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "baseline": {
                    "type": "object",
                    "required": True,
                    "note": "caller-provided tabular baseline for table-diff",
                }
            },
        },
        graph_summary="csv-url sample → table-diff → fresh verdict",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/table-fresh"),
        subtree_contract=subtree_contract_from_policy("orrery/table-fresh"),
    ),
    "orrery/pypi-release": _card(
        summary="Bounded current release metadata for named allowlisted PyPI packages.",
        use_when=(
            "You need the current PyPI release metadata for an allowlisted package",
            "You are gathering release evidence before reasoning",
        ),
        not_for=("Packages outside the allowlist", "Uploading packages", "Dependency resolution"),
        example_intents=("pypi latest version", "allowlisted package release"),
        tools=("get",),
        coverage_slug="pypi-release",
        inputs=(_io("package", "string", required=True),),
        outputs=(_io("release", "object"), *_ENVELOPE),
    ),
    "orrery/npm-release": _card(
        summary="Bounded latest dist-tag metadata for named allowlisted npm packages.",
        use_when=(
            "You need latest dist-tag metadata for an allowlisted npm package",
            "You are gathering release evidence before reasoning",
        ),
        not_for=("Packages outside the allowlist", "Publishing packages", "Lockfile resolution"),
        example_intents=("npm latest dist-tag", "allowlisted npm release"),
        tools=("get",),
        coverage_slug="npm-release",
        inputs=(_io("package", "string", required=True),),
        outputs=(_io("dist_tags", "object"), *_ENVELOPE),
    ),
    "orrery/gh-release-notes": _card(
        summary="Bounded latest release notes for named allowlisted GitHub repositories.",
        use_when=(
            "You need the latest release notes for an allowlisted repo",
            "You want to compare notes against a prior body digest",
        ),
        not_for=("Private repos", "Repos outside the allowlist", "Creating releases"),
        example_intents=("github release notes", "observe latest release body"),
        tools=("observe",),
        coverage_slug="gh-release-notes",
        inputs=(
            _io("target", "string", required=True),
            _io("prior_body_digest", "string"),
        ),
        outputs=(_io("body", "string"), _io("digest", "string"), *_ENVELOPE),
    ),
    "orrery/content-readiness": _card(
        summary="Sync assessment of a caller content bundle into a sealed disposition.",
        use_when=(
            "You need ready | needs-work | inconclusive over structure + bounded links",
            "You want a frozen planner subgraph seal, not a deploy or patch button",
        ),
        not_for=(
            "Durable pause / continuation (sync only)",
            "Write-authority or patch stages",
            "Inventing new subtree field names",
        ),
        example_intents=(
            "content readiness disposition",
            "assess docs bundle structure and links",
            "manifest preflight then structure audit",
        ),
        tools=("run",),
        coverage_slug="content-readiness",
        inputs=(
            _io("files", "array", required=True, note="[{path, content, format?}]"),
            _io(
                "policy",
                "string",
                note="orrery/docs-only@v1 or orrery/max-100-files@v1",
            ),
            _io("max_link_count", "integer", note="1..50; default 20"),
        ),
        outputs=(_io("disposition", "string"), _io("stages", "object"), *_ENVELOPE),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["files"],
            "optional_inputs": ["policy", "max_link_count"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "files": {
                    "type": "array",
                    "required": True,
                    "note": "caller content bundle [{path, content, format?}]",
                },
                "policy": {
                    "type": "string",
                    "required": False,
                    "note": "named preflight policy; default orrery/docs-only@v1",
                },
                "max_link_count": {
                    "type": "integer",
                    "required": False,
                    "note": "bounded link cap for link-check-bounded",
                },
            },
        },
        graph_summary=(
            "manifest-bind → manifest-preflight → structure-audit → "
            "link-check-bounded → artifact-seal"
        ),
        dispositions=CONTENT_READINESS_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/content-readiness"),
        subtree_contract=subtree_contract_from_policy(
            "orrery/content-readiness",
            dispositions=CONTENT_READINESS_DISPOSITIONS,
            pause_allowed=False,
        ),
    ),
    "orrery/authorized-content-patch": _card(
        summary=(
            "Governed content edit path: readiness → write-authority → "
            "patch-capture → sealed composite (never applies patches)."
        ),
        use_when=(
            "You need authorized | denied over readiness + explicit write grant "
            "+ sealed patch digest",
            "You want a frozen edit-path subgraph seal, not a deploy or apply "
            "button",
        ),
        not_for=(
            "Applying patches to the caller filesystem",
            "Publication / deploy (see publish-gate)",
            "Durable pause / continuation (sync only)",
            "Inventing grant schema beyond write-authority-check",
        ),
        example_intents=(
            "authorized content patch",
            "write authority then patch capture",
            "governed docs edit receipt",
        ),
        tools=("run",),
        coverage_slug="authorized-content-patch",
        inputs=(
            _io(
                "before",
                "array",
                required=True,
                note="[{path, content, format?}]; may be empty",
            ),
            _io(
                "after",
                "array",
                required=True,
                note="[{path, content, format?}] assessed for readiness",
            ),
            _io(
                "authority",
                "object",
                required=True,
                note="policy, allowed_paths, grant_digest, optional witness",
            ),
            _io(
                "policy",
                "string",
                note="orrery/docs-only@v1 or orrery/max-100-files@v1",
            ),
            _io("max_link_count", "integer", note="1..50; default 20"),
        ),
        outputs=(
            _io("disposition", "string"),
            _io("stages", "object"),
            *_ENVELOPE,
        ),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["before", "after", "authority"],
            "optional_inputs": ["policy", "max_link_count"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "before": {
                    "type": "array",
                    "required": True,
                    "note": "caller before bundle [{path, content, format?}]",
                },
                "after": {
                    "type": "array",
                    "required": True,
                    "note": "caller after bundle [{path, content, format?}]",
                },
                "authority": {
                    "type": "object",
                    "required": True,
                    "note": "explicit-paths grant (+ optional witness)",
                },
                "policy": {
                    "type": "string",
                    "required": False,
                    "note": "named preflight policy; default orrery/docs-only@v1",
                },
                "max_link_count": {
                    "type": "integer",
                    "required": False,
                    "note": "bounded link cap for link-check-bounded",
                },
            },
        },
        graph_summary=(
            "manifest-bind → manifest-preflight → structure-audit → "
            "link-check-bounded → write-authority-check → patch-capture → "
            "artifact-seal"
        ),
        dispositions=AUTHORIZED_CONTENT_PATCH_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/authorized-content-patch"),
        subtree_contract=subtree_contract_from_policy(
            "orrery/authorized-content-patch",
            dispositions=AUTHORIZED_CONTENT_PATCH_DISPOSITIONS,
            pause_allowed=False,
        ),
    ),
    "orrery/publish-gate": _card(
        summary=(
            "Publication-authority seam: prior edit envelope → publish-profile "
            "write-authority → optional human witness → release seal (no deploy)."
        ),
        use_when=(
            "You need the publish half of the two-phase edit/publish model after "
            "orrery/authorized-content-patch",
            "You want a release seal over publish-profile write-authority without "
            "git push or pages deploy",
        ),
        not_for=(
            "Git push / pages deploy / upload adapters",
            "Edit-path readiness or patch-capture (see authorized-content-patch)",
            "Inventing pause modes beyond ADR 0007 awaiting_witness",
            "Implementing resume MCP continue_run in this leaf",
        ),
        example_intents=(
            "publish gate release seal",
            "two-phase publish authority",
            "awaiting witness publish seam",
        ),
        tools=("run",),
        coverage_slug="publish-gate",
        inputs=(
            _io(
                "prior_envelope",
                "object",
                required=True,
                note="Chirp Envelope wire from authorized-content-patch",
            ),
            _io(
                "authority",
                "object",
                required=True,
                note="profile=publish + explicit-paths grant (+ optional witness)",
            ),
            _io(
                "prior_public_key",
                "string",
                note="optional 64-char hex; verifies prior signature when set",
            ),
            _io(
                "require_witness",
                "boolean",
                note="default false; true → awaiting_witness when missing",
            ),
        ),
        outputs=(
            _io("disposition", "string"),
            _io("stages", "object"),
            *_ENVELOPE,
        ),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["prior_envelope", "authority"],
            "optional_inputs": ["prior_public_key", "require_witness"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "prior_envelope": {
                    "type": "object",
                    "required": True,
                    "note": "prior authorized-content-patch Envelope wire",
                },
                "authority": {
                    "type": "object",
                    "required": True,
                    "note": "publish profile grant (+ optional witness)",
                },
                "prior_public_key": {
                    "type": "string",
                    "required": False,
                    "note": "hex Ed25519 public key for prior verify",
                },
                "require_witness": {
                    "type": "boolean",
                    "required": False,
                    "note": "when true, missing witness seals awaiting_witness",
                },
            },
        },
        graph_summary=(
            "prior-artifact → write-authority-check → human-witness → "
            "artifact-seal"
        ),
        dispositions=PUBLISH_GATE_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/publish-gate"),
        subtree_contract=subtree_contract_from_policy(
            "orrery/publish-gate",
            dispositions=PUBLISH_GATE_DISPOSITIONS,
            pause_allowed=True,
            pause_modes=("awaiting_witness",),
            continuation_tools=("continue_run",),
        ),
    ),
    "orrery/board-memo": _card(
        summary=(
            "Resumable board-memo dogfood: memo-bind → audience-choice pause → "
            "pdf-seal composite with verifiable managed PDF artifact."
        ),
        use_when=(
            "You need ADR 0007 Example 2 pause/resume with one typed choice",
            "You want a checkpointed constellation run ending in html-to-pdf",
            "You need continue_run idempotency without holding a worker lease",
        ),
        not_for=(
            "General workflow authoring or arbitrary graph editing",
            "Holding MCP/HTTP open while awaiting human input",
            "Raw sensitive payloads in default receipts",
        ),
        example_intents=(
            "board memo audience recommendation",
            "resumable constellation pdf seal",
            "awaiting_input board memo demo",
        ),
        tools=("run", "status", "continue_run", "cancel"),
        coverage_slug="board-memo",
        inputs=(
            _io("title", "string", required=True, note="memo title"),
            _io("summary", "string", required=True, note="memo body text"),
            _io("author", "string", note="optional author label"),
            _io("caller_id", "string", note="authenticated resume identity"),
        ),
        outputs=(
            _io("disposition", "string"),
            _io("outstanding_action_requests", "object"),
            _io("artifact_digest", "string"),
            *_ENVELOPE,
        ),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["title", "summary"],
            "optional_inputs": ["author", "caller_id"],
            "composite_output": "signed-envelope-chain",
            "continuation_tools": ["continue_run"],
            "input_bundle": {
                "title": {"type": "string", "required": True},
                "summary": {"type": "string", "required": True},
                "author": {"type": "string", "required": False},
                "caller_id": {"type": "string", "required": False},
            },
        },
        graph_summary="memo-bind → audience-choice → pdf-seal",
        dispositions=BOARD_MEMO_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/board-memo"),
        subtree_contract=subtree_contract_from_policy(
            "orrery/board-memo",
            dispositions=BOARD_MEMO_DISPOSITIONS,
            pause_allowed=True,
            pause_modes=("awaiting_input",),
            continuation_tools=("continue_run",),
        ),
    ),
    "orrery/docs-migrate-to-mdx": _card(
        summary=(
            "Frozen docs/migrate-to-mdx constellation: inventory → profile pin → "
            "safe convert → optional unsupported-decision pause → validate-diff → "
            "composite migration receipt."
        ),
        use_when=(
            "You need ADR 0007/0008 migration orchestration without reimplementing stars",
            "Unsupported MyST semantics require a typed decision before validate/seal",
            "You want continue_run idempotency and digest-bound receipts without raw source",
        ),
        not_for=(
            "Reimplementing inventory/convert/validate stars",
            "Local Git/PR handoff or API-spec upgrade graphs",
            "Holding MCP/HTTP open while awaiting human input",
        ),
        example_intents=(
            "migrate myst docs to mdx with decision pause",
            "docs migrate-to-mdx constellation receipt",
            "continue_run migration checkpoint",
        ),
        tools=("run", "status", "continue_run", "cancel"),
        coverage_slug="docs-migrate-to-mdx",
        inputs=(
            _io("entries", "array", required=True, note="path/content MyST tree"),
            _io("profile", "object", required=True, note="pinned ADR 0008 MigrationProfile"),
            _io("caller_id", "string", note="authenticated resume identity"),
        ),
        outputs=(
            _io("disposition", "string"),
            _io("outstanding_action_requests", "object"),
            _io("migration_receipt", "object"),
            _io("artifact_digest", "string"),
            *_ENVELOPE,
        ),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["entries", "profile"],
            "optional_inputs": ["caller_id"],
            "composite_output": "signed-envelope-chain",
            "continuation_tools": ["continue_run"],
            "input_bundle": {
                "entries": {"type": "array", "required": True},
                "profile": {"type": "object", "required": True},
                "caller_id": {"type": "string", "required": False},
            },
        },
        graph_summary=(
            "inventory → choose-profile → safe-convert → unsupported-decision → "
            "validate-diff → artifact-seal"
        ),
        dispositions=DOCS_MIGRATE_TO_MDX_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/docs-migrate-to-mdx"),
        subtree_contract=subtree_contract_from_policy(
            "orrery/docs-migrate-to-mdx",
            dispositions=DOCS_MIGRATE_TO_MDX_DISPOSITIONS,
            pause_allowed=True,
            pause_modes=("awaiting_input",),
            continuation_tools=("continue_run", "status", "cancel"),
        ),
    ),
    "orrery/api-spec-upgrade": _card(
        summary=(
            "Frozen api-spec/upgrade constellation: inventory → profile pin → "
            "safe upgrade → optional breaking-approval pause → validate-target → "
            "compatibility-diff → composite migration receipt."
        ),
        use_when=(
            "You need ADR 0007/0008 OpenAPI upgrade orchestration without reimplementing stars",
            "Breaking/unknown constructs require typed approval before validate/seal",
            "You want continue_run idempotency and distinct validate vs compatibility-diff digests",
        ),
        not_for=(
            "Reimplementing inventory/upgrade/validate/compatibility-diff stars",
            "Local Git/PR handoff (#180) or docs migrate graphs",
            "Claiming runtime compatibility from structural equality",
        ),
        example_intents=(
            "upgrade openapi 3.0 to 3.1 with breaking pause",
            "api-spec upgrade constellation receipt",
            "continue_run openapi migration checkpoint",
        ),
        tools=("run", "status", "continue_run", "cancel"),
        coverage_slug="api-spec-upgrade",
        inputs=(
            _io("entries", "array", required=True, note="path/content OpenAPI tree"),
            _io("profile", "object", required=True, note="pinned ADR 0008 MigrationProfile"),
            _io("caller_id", "string", note="authenticated resume identity"),
        ),
        outputs=(
            _io("disposition", "string"),
            _io("outstanding_action_requests", "object"),
            _io("migration_receipt", "object"),
            _io("validation_digest", "string"),
            _io("compatibility_diff_digest", "string"),
            _io("artifact_digest", "string"),
            *_ENVELOPE,
        ),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["entries", "profile"],
            "optional_inputs": ["caller_id"],
            "composite_output": "signed-envelope-chain",
            "continuation_tools": ["continue_run"],
            "input_bundle": {
                "entries": {"type": "array", "required": True},
                "profile": {"type": "object", "required": True},
                "caller_id": {"type": "string", "required": False},
            },
        },
        graph_summary=(
            "inventory → choose-profile → safe-upgrade → breaking-approval → "
            "validate-target → compatibility-diff → artifact-seal"
        ),
        dispositions=API_SPEC_UPGRADE_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/api-spec-upgrade"),
        subtree_contract=subtree_contract_from_policy(
            "orrery/api-spec-upgrade",
            dispositions=API_SPEC_UPGRADE_DISPOSITIONS,
            pause_allowed=True,
            pause_modes=("awaiting_input",),
            continuation_tools=("continue_run", "status", "cancel"),
        ),
    ),
    "orrery/ship-check": _card(
        summary=(
            "Seal ship-check evidence: metadata-only (release+UTC) or "
            "content-bundle (content-readiness stages) — one composite receipt."
        ),
        use_when=(
            "You need combined release + source + UTC evidence before reasoning "
            "(mode=metadata, default)",
            "You need a content-bundle readiness seal using content-readiness "
            "stages (mode=content-bundle)",
            "You want a sealed ship-check / content-ship-check receipt, not a "
            "deploy button",
        ),
        not_for=(
            "Deploy approval",
            "Mutating registries",
            "Packages outside allowlists (metadata mode)",
            "Write-authority or patch application (see authorized-content-patch)",
        ),
        example_intents=(
            "ship check evidence",
            "release freshness utc bundle",
            "content ship check on docs bundle",
            "ship check release evidence bundle",
        ),
        tools=("run",),
        coverage_slug="ship-check",
        inputs=(
            _io("package", "string", required=True, note="required for mode=metadata"),
            _io("source_digest", "string"),
            _io(
                "mode",
                "string",
                note="metadata (default) | content-bundle",
            ),
            _io(
                "files",
                "array",
                note="required for mode=content-bundle [{path, content, format?}]",
            ),
            _io("policy", "string", note="content-bundle preflight policy"),
            _io("max_link_count", "integer", note="content-bundle link cap"),
        ),
        outputs=(_io("evidence", "object"), *_ENVELOPE),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["package"],
            "optional_inputs": [
                "source_digest",
                "mode",
                "files",
                "policy",
                "max_link_count",
            ],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "package": {
                    "type": "string",
                    "required": True,
                    "note": "required for mode=metadata (default)",
                },
                "source_digest": {
                    "type": "string",
                    "required": False,
                    "note": "prior digest for source-watch (metadata mode)",
                },
                "mode": {
                    "type": "string",
                    "required": False,
                    "note": "metadata (default) | content-bundle",
                },
                "files": {
                    "type": "array",
                    "required": False,
                    "note": "caller content bundle; required when mode=content-bundle",
                },
                "policy": {
                    "type": "string",
                    "required": False,
                    "note": "named preflight policy; default orrery/docs-only@v1",
                },
                "max_link_count": {
                    "type": "integer",
                    "required": False,
                    "note": "bounded link cap for link-check-bounded",
                },
            },
        },
        graph_summary=(
            "mode=metadata: release metadata → source-watch → world-time → "
            "artifact-seal; mode=content-bundle: manifest-bind → "
            "manifest-preflight → structure-audit → link-check-bounded → "
            "artifact-seal"
        ),
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/ship-check"),
        subtree_contract=subtree_contract_from_policy(
            "orrery/ship-check",
            pause_allowed=False,
            stages=(
                {
                    "id": "release",
                    "label": "release metadata",
                    "role": "gate",
                    "optional": True,
                },
                {
                    "id": "source-watch",
                    "label": "source-watch",
                    "role": "gate",
                    "star_ref": "orrery/source-watch",
                    "optional": True,
                },
                {
                    "id": "world-time",
                    "label": "world-time",
                    "role": "gate",
                    "star_ref": "orrery/world-time",
                    "optional": True,
                },
                {
                    "id": "manifest-bind",
                    "label": "manifest-bind",
                    "role": "gate",
                    "star_ref": "orrery/manifest-bind",
                    "optional": True,
                },
                {
                    "id": "manifest-preflight",
                    "label": "manifest-preflight",
                    "role": "gate",
                    "star_ref": "orrery/manifest-preflight",
                    "optional": True,
                },
                {
                    "id": "structure-audit",
                    "label": "structure-audit",
                    "role": "gate",
                    "star_ref": "orrery/structure-audit",
                    "optional": True,
                },
                {
                    "id": "link-check-bounded",
                    "label": "link-check-bounded",
                    "role": "gate",
                    "star_ref": "orrery/link-check-bounded",
                    "optional": True,
                },
                {
                    "id": "artifact-seal",
                    "label": "artifact-seal",
                    "role": "composite",
                },
            ),
        ),
    ),
    "orrery/stale-proof": _card(
        summary="Fresh UTC plus official Python release-note digest evidence.",
        use_when=(
            "You need to prove a clone cannot mint live truth",
            "You want sealed UTC + official-source digest evidence together",
        ),
        not_for=("Historical clocks", "Arbitrary sources", "Deploy approval"),
        example_intents=(
            "stale proof seal",
            "live utc and release notes digest",
            "release evidence bundle",
        ),
        tools=("run",),
        coverage_slug="stale-proof",
        inputs=(_io("source_digest", "string"),),
        outputs=(_io("evidence", "object"), *_ENVELOPE),
        run_contract={
            "entry_tool": "run",
            "required_inputs": [],
            "optional_inputs": ["source_digest"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "source_digest": {
                    "type": "string",
                    "required": False,
                    "note": "optional prior digest for source-watch diff",
                }
            },
        },
        graph_summary="world-time → source-watch → seal",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/stale-proof"),
        subtree_contract=subtree_contract_from_policy("orrery/stale-proof"),
    ),
    "orrery/csv-report": _card(
        summary="Queue a durable CSV report on Orrery's managed CPU worker.",
        use_when=(
            "You need an async CSV report run with a durable receipt",
            "You are submitting rows and polling for a signed result",
        ),
        not_for=("Synchronous inline renders", "Unbounded row sets", "Direct filesystem writes"),
        example_intents=("queue csv report", "managed csv worker result"),
        tools=("submit", "result"),
        coverage_slug="csv-report",
        inputs=(
            _io("rows", "array", required=True, note="required for submit"),
            _io("idempotency_key", "string", required=True, note="required for submit"),
            _io("run_id", "string", note="required for result"),
        ),
        outputs=(_io("run_id", "string"), *_ENVELOPE),
        write_authority="managed-worker-write",
    ),
    "orrery/image-transform": _card(
        summary="Queue a safe PNG transform on Orrery's managed CPU worker.",
        use_when=(
            "You need a bounded PNG color-fill transform via managed CPU",
            "You are submitting work and polling for a signed result",
        ),
        not_for=("Arbitrary image codecs", "Unbounded uploads", "Direct filesystem writes"),
        example_intents=("queue png transform", "managed image worker result"),
        tools=("submit", "result"),
        coverage_slug="image-transform",
        inputs=(
            _io("color", "string", required=True, note="required for submit"),
            _io("idempotency_key", "string", required=True, note="required for submit"),
            _io("run_id", "string", note="required for result"),
        ),
        outputs=(_io("run_id", "string"), *_ENVELOPE),
        write_authority="managed-worker-write",
    ),
}

_CONSTELLATION_CARDS: dict[str, AgentCard] = {
    "acme/release-gate": _card(
        summary="Private constellation entry for release gating demos.",
        use_when=(
            "You are exploring a private constellation MCP node",
            "You need run/status/explain_policy against a gated graph",
        ),
        not_for=("Public sky calls without namespace access", "Treating this as deploy approval"),
        example_intents=("run release gate", "explain release policy"),
        tools=("run", "status", "explain_policy"),
        coverage_slug="acme-release-gate",
        inputs=(_io("bundle", "object", required=True),),
        outputs=(_io("chain", "signed-envelope-chain"),),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["bundle"],
            "optional_inputs": ["targets"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "pages": {"type": "array", "items": "string"},
                "links": {"type": "array", "items": "string"},
                "examples": {"type": "array", "items": "string"},
            },
        },
        graph_summary="private release gates → status → explain_policy",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=(),
        subtree_contract=subtree_contract_from_policy(
            "acme/release-gate",
            release_digest="sha256:77d0…a19",
            release_key_id="acme-release-1",
            policy_digest="sha256:77d0…a19",
            stages=(
                {
                    "id": "release-gate",
                    "label": "release-gate",
                    "role": "composite",
                },
            ),
        ),
        locality="namespace-private",
        approval="namespace-gated",
    ),
    "acme/launch-gate": _card(
        summary=(
            "Ship policy graph — gates, repair loop, and fan-in disposition "
            "(private acme/* node; may reference public orrery/* stars)."
        ),
        use_when=(
            "You need a composite launch-gate run over a policy graph",
            "You want explain_policy for gates, loops, and fan-in",
            "You are demoing constellation orchestration, not a single star",
            "You need a private-namespace graph that cites public stars (ADR 0004)",
        ),
        not_for=(
            "Public-only agents without acme namespace access",
            "Skipping human-approve witnesses",
            "Treating composite PASS as production deploy authority",
        ),
        example_intents=("run launch gate", "explain ship policy", "constellation status"),
        tools=("run", "status", "explain_policy"),
        coverage_slug="acme-launch-gate",
        inputs=(
            _io("bundle", "object", required=True, note="Doc Bundle: pages, links, examples"),
            _io("targets", "array"),
        ),
        outputs=(_io("chain", "signed-envelope-chain"),),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["bundle"],
            "optional_inputs": ["targets", "constellation"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "pages": {"type": "array", "items": "string"},
                "links": {"type": "array", "items": "string"},
                "examples": {"type": "array", "items": "string"},
            },
        },
        graph_summary="secret-scan → license → html-to-pdf → human-approve fan-in",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=member_stars_from_policy("acme/launch-gate"),
        subtree_contract=subtree_contract_from_policy("acme/launch-gate"),
        locality="namespace-private",
        approval="human-approve-witness",
    ),
}

AGENT_CARDS: dict[str, AgentCard] = {**_STAR_CARDS, **_CONSTELLATION_CARDS}


def card_for(name: str) -> AgentCard | None:
    """Return the registered agent card for a resolvable name, if any."""
    return AGENT_CARDS.get(name)


def require_card(name: str) -> AgentCard:
    """Return a validated card or raise if missing/invalid."""
    card = card_for(name)
    if card is None:
        raise AgentCardError(f"missing agent card for {name!r}")
    validate_agent_card(card, name=name)
    return card


def assert_registry_complete(names: tuple[str, ...] | list[str]) -> None:
    """CI guard: every required public name has a valid agent card."""
    missing: list[str] = []
    invalid: list[str] = []
    for name in names:
        card = card_for(name)
        if card is None:
            missing.append(name)
            continue
        try:
            validate_agent_card(card, name=name)
        except AgentCardError as error:
            invalid.append(f"{name}: {error}")
    if missing or invalid:
        parts: list[str] = []
        if missing:
            parts.append(f"missing cards: {missing}")
        if invalid:
            parts.append(f"invalid cards: {invalid}")
        raise AgentCardError("; ".join(parts))


def required_public_card_names() -> tuple[str, ...]:
    """Names that must carry agent cards (builtin stars + constellation seeds)."""
    from stars._core.registry import load_builtin_star_definition
    from stars.builtins import BUILTIN_STAR_PACKAGES

    from .fixtures import CONSTELLATION_SEEDS

    star_names = tuple(
        sorted(load_builtin_star_definition(package).name for package in BUILTIN_STAR_PACKAGES)
    )
    constellation_names = tuple(record.name for record in CONSTELLATION_SEEDS)
    return star_names + constellation_names
