"""Constellation policy graphs — gates, repair loops, fan-in (#31).

Policy graph model for the viewer; orchestration lives in
``catalog.constellation_run`` (#33).
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

#: Cohort A parable — seal fresh UTC and fixed-source digest evidence (#88).
STALE_PROOF_POLICY = PolicyGraph(
    nodes=(
        PolicyNode(
            id="world-time",
            label="world-time",
            node_kind="gate",
            star_ref="orrery/world-time",
            x=180,
            y=200,
            step=0,
            status_label="now",
        ),
        PolicyNode(
            id="source-watch",
            label="source-watch",
            node_kind="gate",
            star_ref="orrery/source-watch",
            x=420,
            y=200,
            step=1,
            status_label="observe",
        ),
        PolicyNode(
            id="seal",
            label="seal",
            node_kind="composite",
            x=650,
            y=360,
            step=2,
            status_label="composite",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            id="sp3a",
            source="source-watch",
            target="seal",
            kind="fan_in",
            path_d="M420 240 C480 300, 560 320, 630 340",
            step=2,
            stroke="#9aafc2",
            stroke_width=1.4,
        ),
        PolicyEdge(
            id="sp3c",
            source="world-time",
            target="seal",
            kind="fan_in",
            path_d="M180 240 C180 340, 400 380, 590 360",
            step=2,
            stroke="#9aafc2",
            stroke_width=1.2,
            opacity=0.55,
        ),
    ),
    repair_loop_max=None,
    footnote=(
        "Two live components · clone fails: offline copies cannot mint fresh UTC "
        "or re-observe the official source. Optional PDF is a separate managed Star."
    ),
    composite_chain=(
        CompositeStep(1, "world-time", "Envelope ✓", "now"),
        CompositeStep(2, "source-watch", "Envelope ✓", "observe/diff"),
    ),
    release_digest="sha256:stale…",
    release_key_id="orrery-stale-proof-1",
)

TABLE_FRESH_POLICY = PolicyGraph(
    nodes=(
        PolicyNode("csv-url", "csv-url", "gate", 180, 200, 0, "orrery/csv-url", "fresh"),
        PolicyNode("table-diff", "table-diff", "gate", 460, 200, 1, "orrery/table-diff", "compare"),
        PolicyNode(
            "fresh-verdict",
            "fresh verdict",
            "composite",
            760,
            300,
            2,
            status_label="composite",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            "tf1", "csv-url", "table-diff", "gate", "M220 200 C300 200, 340 200, 420 200", 1
        ),
        PolicyEdge(
            "tf2", "table-diff", "fresh-verdict", "gate", "M500 220 C590 270, 650 290, 720 300", 2
        ),
    ),
    repair_loop_max=None,
    footnote="Fresh source evidence → bounded route diff → signed verdict (100-row sample).",
    composite_chain=(
        CompositeStep(1, "csv-url", "Envelope ✓", "fresh flights-airport sample"),
        CompositeStep(2, "table-diff", "Envelope ✓", "route-key comparison"),
    ),
    release_digest="sha256:table-fresh…",
    release_key_id="orrery-table-fresh-1",
)

SHIP_CHECK_POLICY = PolicyGraph(
    nodes=(
        PolicyNode("release", "release metadata", "gate", 130, 180, 0, status_label="release"),
        PolicyNode(
            "source-watch", "source-watch", "gate", 390, 180, 1, "orrery/source-watch", "fresh"
        ),
        PolicyNode("world-time", "world-time", "gate", 630, 180, 2, "orrery/world-time", "UTC"),
        PolicyNode("reason", "reason", "composite", 820, 300, 3, status_label="composite", r=18),
    ),
    edges=(
        PolicyEdge(
            "sc1", "release", "source-watch", "gate", "M170 180 C250 180, 290 180, 350 180", 1
        ),
        PolicyEdge(
            "sc2", "source-watch", "world-time", "gate", "M430 180 C510 180, 550 180, 590 180", 2
        ),
        PolicyEdge("sc3", "world-time", "reason", "gate", "M670 200 C730 250, 770 280, 790 290", 3),
    ),
    repair_loop_max=None,
    footnote="Release metadata + source change evidence + UTC; never deploy approval.",
    composite_chain=(
        CompositeStep(1, "release", "Envelope ✓", "PyPI/npm latest"),
        CompositeStep(2, "source-watch", "Envelope ✓", "Python notes diff"),
        CompositeStep(3, "world-time", "Envelope ✓", "UTC evidence"),
    ),
    release_digest="sha256:ship-check…",
    release_key_id="orrery-ship-check-1",
)

POLICIES: dict[str, PolicyGraph] = {
    "acme/launch-gate": LAUNCH_GATE_POLICY,
    "orrery/stale-proof": STALE_PROOF_POLICY,
    "orrery/table-fresh": TABLE_FRESH_POLICY,
    "orrery/ship-check": SHIP_CHECK_POLICY,
}


def policy_for(name: str) -> PolicyGraph | None:
    """Return the policy graph for a constellation name, if defined."""
    return POLICIES.get(name)
