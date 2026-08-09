"""Constellation policy graphs — gates, repair loops, fan-in (#31).

Read-only model for the graph viewer. Orchestration ``run`` MCP is Wave 4 (#33).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EdgeKind = Literal["gate", "repair_loop", "fan_in"]
NodeKind = Literal["gate", "witness", "composite", "internal"]


@dataclass(frozen=True, slots=True)
class PolicyNode:
    """One step in a constellation policy graph."""

    id: str
    label: str
    node_kind: NodeKind
    x: int
    y: int
    step: int
    star_ref: str | None = None
    status_label: str = "PASS"
    r: int = 14


@dataclass(frozen=True, slots=True)
class PolicyEdge:
    """Directed edge between policy nodes (SVG path + semantics)."""

    id: str
    source: str
    target: str
    kind: EdgeKind
    path_d: str
    step: int
    stroke: str = "#c4a06a"
    stroke_width: float = 1.6
    marker: str = "arrow"
    opacity: float = 1.0


@dataclass(frozen=True, slots=True)
class CompositeStep:
    """One line in a demo composite receipt chain."""

    order: int
    label: str
    status: str
    note: str


@dataclass(frozen=True, slots=True)
class PolicyGraph:
    """Full policy graph for a constellation record."""

    nodes: tuple[PolicyNode, ...]
    edges: tuple[PolicyEdge, ...]
    repair_loop_max: int | None
    footnote: str
    composite_chain: tuple[CompositeStep, ...]
    release_digest: str
    release_key_id: str


LAUNCH_GATE_POLICY = PolicyGraph(
    nodes=(
        PolicyNode(
            id="secret-scan",
            label="secret-scan",
            node_kind="gate",
            star_ref="acme/secret-scan",
            x=170,
            y=160,
            step=0,
        ),
        PolicyNode(
            id="license",
            label="license",
            node_kind="gate",
            star_ref="acme/license-check",
            x=400,
            y=160,
            step=1,
        ),
        PolicyNode(
            id="html-to-pdf",
            label="html-to-pdf*",
            node_kind="gate",
            star_ref="orrery/html-to-pdf",
            x=680,
            y=160,
            step=2,
        ),
        PolicyNode(
            id="human-approve",
            label="human-approve",
            node_kind="witness",
            star_ref="acme/human-approve",
            x=560,
            y=380,
            step=3,
            status_label="witness",
            r=16,
        ),
        PolicyNode(
            id="release",
            label="release",
            node_kind="composite",
            x=820,
            y=400,
            step=4,
            status_label="composite",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            id="e1",
            source="secret-scan",
            target="license",
            kind="gate",
            path_d="M170 160 C260 160, 260 160, 340 160",
            step=1,
        ),
        PolicyEdge(
            id="e2",
            source="license",
            target="html-to-pdf",
            kind="gate",
            path_d="M460 160 C540 160, 540 160, 620 160",
            step=2,
        ),
        PolicyEdge(
            id="e3a",
            source="html-to-pdf",
            target="human-approve",
            kind="fan_in",
            path_d="M740 200 C780 280, 780 300, 700 360",
            step=3,
            stroke="#9aafc2",
            stroke_width=1.4,
        ),
        PolicyEdge(
            id="e3b",
            source="license",
            target="human-approve",
            kind="fan_in",
            path_d="M400 220 C400 300, 400 300, 520 360",
            step=3,
            stroke="#9aafc2",
            stroke_width=1.4,
        ),
        PolicyEdge(
            id="e3c",
            source="secret-scan",
            target="human-approve",
            kind="fan_in",
            path_d="M170 200 C170 300, 280 360, 520 380",
            step=3,
            stroke="#9aafc2",
            stroke_width=1.3,
            opacity=0.7,
        ),
        PolicyEdge(
            id="loop",
            source="license",
            target="secret-scan",
            kind="repair_loop",
            path_d="M340 200 C300 280, 220 280, 170 200",
            step=2,
            stroke="#7ec8a3",
            marker="arrow-g",
        ),
        PolicyEdge(
            id="e4",
            source="human-approve",
            target="release",
            kind="gate",
            path_d="M560 400 C640 430, 720 430, 780 400",
            step=4,
            stroke_width=1.8,
        ),
    ),
    repair_loop_max=3,
    footnote="* demo star in public namespace · loop retries secret-scan ≤ 3",
    composite_chain=(
        CompositeStep(1, "secret-scan", "Envelope ✓", "pay_01"),
        CompositeStep(2, "license", "Envelope ✓", "(internal)"),
        CompositeStep(3, "html-to-pdf", "Envelope ✓", "pay_02"),
        CompositeStep(4, "human-approve", "Envelope ✓", "witness"),
    ),
    release_digest="sha256:aa11…",
    release_key_id="acme-release-1",
)

POLICIES: dict[str, PolicyGraph] = {
    "acme/launch-gate": LAUNCH_GATE_POLICY,
}


def policy_for(name: str) -> PolicyGraph | None:
    """Return the policy graph for a constellation name, if defined."""
    return POLICIES.get(name)
