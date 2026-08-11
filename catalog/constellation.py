"""Constellation policy graphs — gates, repair loops, fan-in (#31).

Policy graph model for the viewer; orchestration lives in
``catalog.constellation_run`` (#33).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EdgeKind = Literal["gate", "repair_loop", "fan_in"]
NodeKind = Literal["gate", "witness", "composite", "internal", "pause"]


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
    footnote=(
        "* public star ref (orrery/html-to-pdf) from private acme/* graph — "
        "ADR 0004 publisher-direct · loop retries secret-scan ≤ 3"
    ),
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

#: Dual-mode ship-check / content-ship-check (#214): metadata path + content-
#: readiness stage vocabulary; mode selected via run input; sync only.
SHIP_CHECK_POLICY = PolicyGraph(
    nodes=(
        PolicyNode("release", "release metadata", "gate", 100, 120, 0, status_label="release"),
        PolicyNode(
            "source-watch", "source-watch", "gate", 300, 120, 1, "orrery/source-watch", "fresh"
        ),
        PolicyNode("world-time", "world-time", "gate", 500, 120, 2, "orrery/world-time", "UTC"),
        PolicyNode(
            "manifest-bind",
            "manifest-bind",
            "gate",
            100,
            280,
            3,
            "orrery/manifest-bind",
            "bind",
        ),
        PolicyNode(
            "manifest-preflight",
            "manifest-preflight",
            "gate",
            300,
            280,
            4,
            "orrery/manifest-preflight",
            "preflight",
        ),
        PolicyNode(
            "structure-audit",
            "structure-audit",
            "gate",
            500,
            280,
            5,
            "orrery/structure-audit",
            "audit",
        ),
        PolicyNode(
            "link-check-bounded",
            "link-check-bounded",
            "gate",
            700,
            280,
            6,
            "orrery/link-check-bounded",
            "links",
        ),
        PolicyNode(
            "artifact-seal",
            "artifact-seal",
            "composite",
            820,
            200,
            7,
            status_label="composite",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            "sc1", "release", "source-watch", "gate", "M140 120 C200 120, 240 120, 260 120", 1
        ),
        PolicyEdge(
            "sc2", "source-watch", "world-time", "gate", "M340 120 C400 120, 440 120, 460 120", 2
        ),
        PolicyEdge(
            "sc3", "world-time", "artifact-seal", "gate", "M540 140 C640 160, 740 180, 790 190", 3
        ),
        PolicyEdge(
            "sc4",
            "manifest-bind",
            "manifest-preflight",
            "gate",
            "M140 280 C200 280, 240 280, 260 280",
            4,
        ),
        PolicyEdge(
            "sc5",
            "manifest-preflight",
            "structure-audit",
            "gate",
            "M340 280 C400 280, 440 280, 460 280",
            5,
        ),
        PolicyEdge(
            "sc6",
            "structure-audit",
            "link-check-bounded",
            "gate",
            "M540 280 C600 280, 640 280, 660 280",
            6,
        ),
        PolicyEdge(
            "sc7",
            "link-check-bounded",
            "artifact-seal",
            "gate",
            "M740 260 C780 240, 800 220, 810 210",
            7,
        ),
    ),
    repair_loop_max=None,
    footnote=(
        "Dual mode (run input): metadata = release→source-watch→world-time→seal; "
        "content-bundle = content-readiness stages→seal. Sync only; never deploy."
    ),
    composite_chain=(
        CompositeStep(1, "release", "Envelope ✓", "PyPI/npm latest (metadata)"),
        CompositeStep(2, "source-watch", "Envelope ✓", "Python notes diff"),
        CompositeStep(3, "world-time", "Envelope ✓", "UTC evidence"),
        CompositeStep(4, "manifest-bind", "Envelope ✓", "content-bundle inventory"),
        CompositeStep(5, "link-check-bounded", "Envelope ✓", "bounded HTTPS"),
    ),
    release_digest="sha256:ship-check…",
    release_key_id="orrery-ship-check-1",
)

#: ADR 0007 Example 1 — sync content-readiness (#213); pause never allowed.
CONTENT_READINESS_POLICY = PolicyGraph(
    nodes=(
        PolicyNode(
            "manifest-bind",
            "manifest-bind",
            "gate",
            100,
            180,
            0,
            "orrery/manifest-bind",
            "bind",
        ),
        PolicyNode(
            "manifest-preflight",
            "manifest-preflight",
            "gate",
            300,
            180,
            1,
            "orrery/manifest-preflight",
            "preflight",
        ),
        PolicyNode(
            "structure-audit",
            "structure-audit",
            "gate",
            500,
            180,
            2,
            "orrery/structure-audit",
            "audit",
        ),
        PolicyNode(
            "link-check-bounded",
            "link-check-bounded",
            "gate",
            700,
            180,
            3,
            "orrery/link-check-bounded",
            "links",
        ),
        PolicyNode(
            "artifact-seal",
            "artifact-seal",
            "composite",
            880,
            320,
            4,
            status_label="composite",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            "cr1",
            "manifest-bind",
            "manifest-preflight",
            "gate",
            "M140 180 C200 180, 240 180, 260 180",
            1,
        ),
        PolicyEdge(
            "cr2",
            "manifest-preflight",
            "structure-audit",
            "gate",
            "M340 180 C400 180, 440 180, 460 180",
            2,
        ),
        PolicyEdge(
            "cr3",
            "structure-audit",
            "link-check-bounded",
            "gate",
            "M540 180 C600 180, 640 180, 660 180",
            3,
        ),
        PolicyEdge(
            "cr4",
            "link-check-bounded",
            "artifact-seal",
            "gate",
            "M740 200 C800 260, 840 300, 860 310",
            4,
        ),
    ),
    repair_loop_max=None,
    footnote=(
        "Sync only (pause_policy.allowed=false) · dispositions ready|needs-work|inconclusive · "
        "composite seal in-package (no artifact-seal star)."
    ),
    composite_chain=(
        CompositeStep(1, "manifest-bind", "Envelope ✓", "digest inventory"),
        CompositeStep(2, "manifest-preflight", "Envelope ✓", "named policy"),
        CompositeStep(3, "structure-audit", "Envelope ✓", "markdown findings"),
        CompositeStep(4, "link-check-bounded", "Envelope ✓", "bounded HTTPS"),
    ),
    release_digest="sha256:content-readiness…",
    release_key_id="orrery-content-readiness-1",
)

#: ADR 0007 — sync authorized-content-patch (#215); readiness → grant → capture.
AUTHORIZED_CONTENT_PATCH_POLICY = PolicyGraph(
    nodes=(
        PolicyNode(
            "manifest-bind",
            "manifest-bind",
            "gate",
            80,
            180,
            0,
            "orrery/manifest-bind",
            "bind",
        ),
        PolicyNode(
            "manifest-preflight",
            "manifest-preflight",
            "gate",
            220,
            180,
            1,
            "orrery/manifest-preflight",
            "preflight",
        ),
        PolicyNode(
            "structure-audit",
            "structure-audit",
            "gate",
            360,
            180,
            2,
            "orrery/structure-audit",
            "audit",
        ),
        PolicyNode(
            "link-check-bounded",
            "link-check-bounded",
            "gate",
            500,
            180,
            3,
            "orrery/link-check-bounded",
            "links",
        ),
        PolicyNode(
            "write-authority-check",
            "write-authority-check",
            "gate",
            640,
            180,
            4,
            "orrery/write-authority-check",
            "grant",
        ),
        PolicyNode(
            "patch-capture",
            "patch-capture",
            "gate",
            780,
            180,
            5,
            "orrery/patch-capture",
            "capture",
        ),
        PolicyNode(
            "artifact-seal",
            "artifact-seal",
            "composite",
            900,
            320,
            6,
            status_label="composite",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            "acp1",
            "manifest-bind",
            "manifest-preflight",
            "gate",
            "M120 180 C160 180, 180 180, 200 180",
            1,
        ),
        PolicyEdge(
            "acp2",
            "manifest-preflight",
            "structure-audit",
            "gate",
            "M260 180 C300 180, 320 180, 340 180",
            2,
        ),
        PolicyEdge(
            "acp3",
            "structure-audit",
            "link-check-bounded",
            "gate",
            "M400 180 C440 180, 460 180, 480 180",
            3,
        ),
        PolicyEdge(
            "acp4",
            "link-check-bounded",
            "write-authority-check",
            "gate",
            "M540 180 C580 180, 600 180, 620 180",
            4,
        ),
        PolicyEdge(
            "acp5",
            "write-authority-check",
            "patch-capture",
            "gate",
            "M680 180 C720 180, 740 180, 760 180",
            5,
        ),
        PolicyEdge(
            "acp6",
            "patch-capture",
            "artifact-seal",
            "gate",
            "M820 200 C860 260, 880 300, 890 310",
            6,
        ),
    ),
    repair_loop_max=None,
    footnote=(
        "Sync only · readiness→write-authority→patch-capture→seal · "
        "never applies patches to caller filesystem · publish-gate is separate."
    ),
    composite_chain=(
        CompositeStep(1, "manifest-bind", "Envelope ✓", "after inventory"),
        CompositeStep(2, "manifest-preflight", "Envelope ✓", "named policy"),
        CompositeStep(3, "structure-audit", "Envelope ✓", "markdown findings"),
        CompositeStep(4, "link-check-bounded", "Envelope ✓", "bounded HTTPS"),
        CompositeStep(5, "write-authority-check", "Envelope ✓", "explicit grant"),
        CompositeStep(6, "patch-capture", "Envelope ✓", "before/after digest"),
    ),
    release_digest="sha256:authorized-content-patch…",
    release_key_id="orrery-authorized-content-patch-1",
)

#: ADR 0007 — publish-gate (#216); prior envelope → publish grant → optional witness.
PUBLISH_GATE_POLICY = PolicyGraph(
    nodes=(
        PolicyNode(
            "prior-artifact",
            "prior-artifact",
            "gate",
            160,
            180,
            0,
            status_label="prior",
        ),
        PolicyNode(
            "write-authority-check",
            "write-authority-check",
            "gate",
            380,
            180,
            1,
            "orrery/write-authority-check",
            "grant",
        ),
        PolicyNode(
            "human-witness",
            "human-witness",
            "witness",
            600,
            180,
            2,
            status_label="witness",
            r=16,
        ),
        PolicyNode(
            "artifact-seal",
            "artifact-seal",
            "composite",
            820,
            320,
            3,
            status_label="composite",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            "pg1",
            "prior-artifact",
            "write-authority-check",
            "gate",
            "M200 180 C260 180, 300 180, 340 180",
            1,
        ),
        PolicyEdge(
            "pg2",
            "write-authority-check",
            "human-witness",
            "gate",
            "M420 180 C480 180, 520 180, 560 180",
            2,
        ),
        PolicyEdge(
            "pg3",
            "human-witness",
            "artifact-seal",
            "gate",
            "M640 200 C700 260, 760 300, 800 310",
            3,
        ),
    ),
    repair_loop_max=None,
    footnote=(
        "Two-phase publish seam · pause_policy.allowed=true (awaiting_witness) · "
        "no git push / pages deploy · lease_rule waiting_never_holds_worker_lease."
    ),
    composite_chain=(
        CompositeStep(1, "prior-artifact", "Envelope ✓", "authorized edit prior"),
        CompositeStep(2, "write-authority-check", "Envelope ✓", "publish profile grant"),
        CompositeStep(3, "human-witness", "optional", "awaiting_witness if required"),
    ),
    release_digest="sha256:publish-gate…",
    release_key_id="orrery-publish-gate-1",
)

#: ADR 0007 Example 2 — board-memo (#154); pause for audience/recommendation → PDF seal.
BOARD_MEMO_POLICY = PolicyGraph(
    nodes=(
        PolicyNode(
            "memo-bind",
            "memo-bind",
            "gate",
            160,
            180,
            0,
            status_label="bound",
        ),
        PolicyNode(
            "audience-choice",
            "audience-choice",
            "pause",
            400,
            180,
            1,
            status_label="pause",
        ),
        PolicyNode(
            "pdf-seal",
            "pdf-seal",
            "composite",
            680,
            320,
            2,
            "orrery/html-to-pdf",
            "seal",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            "bm1",
            "memo-bind",
            "audience-choice",
            "gate",
            "M240 180 C300 180, 340 180, 360 180",
            1,
        ),
        PolicyEdge(
            "bm2",
            "audience-choice",
            "pdf-seal",
            "gate",
            "M480 180 C540 220, 600 280, 660 300",
            2,
        ),
    ),
    repair_loop_max=None,
    footnote=(
        "Resumable board memo · pause_policy.allowed=true (awaiting_input) · "
        "continue_run resumes · PDF via html-to-pdf · "
        "lease_rule waiting_never_holds_worker_lease."
    ),
    composite_chain=(
        CompositeStep(1, "memo-bind", "Envelope ✓", "title+summary bound"),
        CompositeStep(2, "audience-choice", "awaiting_input", "typed choice"),
        CompositeStep(3, "pdf-seal", "Envelope ✓", "managed PDF artifact"),
    ),
    release_digest="sha256:board-memo…",
    release_key_id="orrery-board-memo-1",
)

#: ADR 0007 / epic #164 — docs migrate-to-MDX frozen graph (#178).
DOCS_MIGRATE_TO_MDX_POLICY = PolicyGraph(
    nodes=(
        PolicyNode(
            "inventory",
            "inventory",
            "gate",
            80,
            180,
            0,
            "orrery/docs-myst-inventory",
            "inventory",
        ),
        PolicyNode(
            "choose-profile",
            "choose-profile",
            "gate",
            220,
            180,
            1,
            status_label="profile",
        ),
        PolicyNode(
            "safe-convert",
            "safe-convert",
            "gate",
            360,
            180,
            2,
            "orrery/docs-myst-to-mdx-safe",
            "convert",
        ),
        PolicyNode(
            "unsupported-decision",
            "unsupported-decision",
            "pause",
            500,
            180,
            3,
            status_label="pause",
        ),
        PolicyNode(
            "validate-diff",
            "validate-diff",
            "gate",
            640,
            180,
            4,
            "orrery/docs-mdx-validate-and-migration-diff",
            "validate",
        ),
        PolicyNode(
            "artifact-seal",
            "artifact-seal",
            "composite",
            780,
            320,
            5,
            status_label="seal",
            r=18,
        ),
    ),
    edges=(
        PolicyEdge(
            "dm1",
            "inventory",
            "choose-profile",
            "gate",
            "M120 180 C170 180, 190 180, 200 180",
            1,
        ),
        PolicyEdge(
            "dm2",
            "choose-profile",
            "safe-convert",
            "gate",
            "M260 180 C310 180, 330 180, 340 180",
            2,
        ),
        PolicyEdge(
            "dm3",
            "safe-convert",
            "unsupported-decision",
            "gate",
            "M400 180 C450 180, 470 180, 480 180",
            3,
        ),
        PolicyEdge(
            "dm4",
            "unsupported-decision",
            "validate-diff",
            "gate",
            "M540 180 C590 180, 610 180, 620 180",
            4,
        ),
        PolicyEdge(
            "dm5",
            "validate-diff",
            "artifact-seal",
            "gate",
            "M680 180 C730 220, 750 280, 760 300",
            5,
        ),
    ),
    repair_loop_max=None,
    footnote=(
        "Frozen MyST→MDX migration · pause when decision_required · "
        "continue_run resumes · composite migration receipt · "
        "lease_rule waiting_never_holds_worker_lease."
    ),
    composite_chain=(
        CompositeStep(1, "inventory", "Envelope ✓", "source inventory"),
        CompositeStep(2, "choose-profile", "Envelope ✓", "profile pin"),
        CompositeStep(3, "safe-convert", "Envelope ✓", "plan+apply"),
        CompositeStep(4, "unsupported-decision", "awaiting_input", "typed decision"),
        CompositeStep(5, "validate-diff", "Envelope ✓", "validate+diff"),
        CompositeStep(6, "artifact-seal", "Envelope ✓", "migration receipt"),
    ),
    release_digest="sha256:docs-migrate-to-mdx…",
    release_key_id="orrery-docs-migrate-to-mdx-1",
)

POLICIES: dict[str, PolicyGraph] = {
    "acme/launch-gate": LAUNCH_GATE_POLICY,
    "orrery/stale-proof": STALE_PROOF_POLICY,
    "orrery/table-fresh": TABLE_FRESH_POLICY,
    "orrery/ship-check": SHIP_CHECK_POLICY,
    "orrery/content-readiness": CONTENT_READINESS_POLICY,
    "orrery/authorized-content-patch": AUTHORIZED_CONTENT_PATCH_POLICY,
    "orrery/publish-gate": PUBLISH_GATE_POLICY,
    "orrery/board-memo": BOARD_MEMO_POLICY,
    "orrery/docs-migrate-to-mdx": DOCS_MIGRATE_TO_MDX_POLICY,
}


def policy_for(name: str) -> PolicyGraph | None:
    """Return the policy graph for a constellation name, if defined."""
    return POLICIES.get(name)
