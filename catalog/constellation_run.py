"""Constellation orchestration — ``run`` / ``status`` / ``explain_policy`` (#33).

Steps are stubbed; each gate emits a real signed Envelope in the composite
chain. Run state is in-memory for the process lifetime (Wave 4 demo).
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Any, Literal

from chirp.skill import sign_envelope

from catalog.constellation import PolicyGraph, policy_for

RunStatus = Literal["in_flight", "completed"]


@dataclass(slots=True)
class RunState:
    """One constellation execution and its composite receipt chain."""

    run_id: str
    constellation: str
    status: RunStatus
    bundle: dict[str, Any]
    policy_digest: str
    chain: tuple[dict[str, Any], ...]
    release: dict[str, str]


_RUNS: dict[str, RunState] = {}
_latest_run_id: str | None = None


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


def explain_policy(name: str = "acme/launch-gate") -> dict[str, Any]:
    """Plain-language gates, repair loops, and fan-in for a constellation."""
    graph = policy_for(name)
    if graph is None:
        return {"error": "not_found", "name": name, "status": "not_found"}

    gate_nodes = sorted(
        (n for n in graph.nodes if n.node_kind in ("gate", "witness")),
        key=lambda n: n.step,
    )
    repair = next((e for e in graph.edges if e.kind == "repair_loop"), None)
    fan_in: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.kind == "fan_in":
            fan_in.setdefault(edge.target, []).append(edge.source)

    narrative: list[str] = [
        f"Constellation {name} evaluates {len(gate_nodes)} gates before release.",
        "Gate order: " + " → ".join(n.label for n in gate_nodes) + " → release.",
    ]
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

    return {
        "constellation": name,
        "status": "ok",
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


def run_constellation(
    bundle: dict[str, Any],
    *,
    constellation: str,
    skill_name: str,
    skill_version: str,
    key_id: str,
    private_key: Any,
) -> dict[str, Any]:
    """Execute a constellation on a Doc Bundle and return the composite chain."""
    global _latest_run_id

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
    )
    _RUNS[run_id] = state
    _latest_run_id = run_id

    return {
        "constellation": constellation,
        "run_id": run_id,
        "policy_digest": policy_d,
        "status": "completed",
        "bundle": bundle,
        "chain": chain,
        "release": state.release,
    }


def status_for_run(run_id: str = "") -> dict[str, Any]:
    """Return in-flight or completed composite receipt for a run."""
    resolved = run_id.strip() or (_latest_run_id or "")
    if not resolved:
        return {"error": "not_found", "run_id": run_id, "status": "not_found"}

    state = _RUNS.get(resolved)
    if state is None:
        return {"error": "not_found", "run_id": resolved, "status": "not_found"}

    return {
        "run_id": state.run_id,
        "constellation": state.constellation,
        "status": state.status,
        "policy_digest": state.policy_digest,
        "bundle": state.bundle,
        "chain": list(state.chain),
        "release": state.release,
    }
