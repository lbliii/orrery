"""Publish-oracle status for resolve rows and star pages (#34).

Reads the host :class:`~chirp.skill.publish.PublishReceipt` (check → freeze →
smoke) and per-skill :class:`~chirp.skill.console.ReliabilityScore` values so
public oracle pills agree with ``/console``.

Host product readiness is **check + freeze** only. Smoke is attributed per
skill via :data:`TOOL_SKILL` so one corpus miss does not paint every star.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chirp.skill.console import ReliabilityScore
from chirp.skill.publish import STAGE_CHECK, STAGE_FREEZE
from chirp.skill.smoke import SmokeReport

if TYPE_CHECKING:
    from chirp.skill.console import ReliabilityStore
    from chirp.skill.publish import PublishReceipt
    from chirp.skill.registry import SkillRegistry

    from catalog.models import ResolveRecord

#: Resolve catalog name → mounted dogfood skill name (public callable stars).
RECORD_SKILL: dict[str, str] = {
    "orrery/html-to-pdf": "html-to-pdf",
    "orrery/world-time": "world-time",
    "orrery/source-watch": "source-watch",
}

#: MCP tool → owning skill (for per-skill smoke attribution).
TOOL_SKILL: dict[str, str] = {
    "gaze_match": "gaze",
    "gaze_search": "gaze",
    "gaze_describe": "gaze",
    "gaze_list_constellations": "gaze",
    "resolve_name": "resolve",
    "convert": "html-to-pdf",
    "health": "html-to-pdf",
    "fetch": "world-time",
    "get": "world-time",
    "answer": "world-time",
    "observe": "source-watch",
    "diff": "source-watch",
    "source_watch_answer": "source-watch",
    "run": "launch-gate",
    "status": "launch-gate",
    "explain_policy": "launch-gate",
}

#: Publish-gate stages that gate the *host* (product chrome), not per-skill smoke.
_HOST_STAGES: frozenset[str] = frozenset({STAGE_CHECK, STAGE_FREEZE})

_receipt: PublishReceipt | None = None
_scores: ReliabilityStore | None = None


def configure_oracle(
    *,
    receipt: PublishReceipt | None,
    scores: ReliabilityStore | None,
) -> None:
    """Bind publish-oracle outputs for the process lifetime."""
    global _receipt, _scores
    _receipt = receipt
    _scores = scores


def smoke_slice_for_skill(report: SmokeReport, skill_name: str) -> SmokeReport | None:
    """Return smoke results owned by ``skill_name``, or ``None`` if none."""
    results = tuple(r for r in report.results if TOOL_SKILL.get(r.tool) == skill_name)
    if not results:
        return None
    return SmokeReport(results=results)


def record_skill_scores(
    scores: ReliabilityStore,
    report: SmokeReport,
    *,
    skill_names: tuple[str, ...] | None = None,
) -> dict[str, ReliabilityScore]:
    """Record per-skill :class:`ReliabilityScore` slices into ``scores``.

    Skills with no corpus prompts are left unscored (unknown). When
    ``skill_names`` is omitted, every skill that owns at least one result in
    ``report`` is recorded.
    """
    if skill_names is None:
        names = tuple(sorted({TOOL_SKILL[r.tool] for r in report.results if r.tool in TOOL_SKILL}))
    else:
        names = skill_names

    recorded: dict[str, ReliabilityScore] = {}
    for name in names:
        sliced = smoke_slice_for_skill(report, name)
        if sliced is None:
            continue
        recorded[name] = scores.record(name, sliced)
    return recorded


def record_skill_scores_from_registry(
    scores: ReliabilityStore,
    report: SmokeReport,
    registry: SkillRegistry,
) -> dict[str, ReliabilityScore]:
    """Record slices for every skill currently mounted on ``registry``."""
    return record_skill_scores(
        scores,
        report,
        skill_names=tuple(s.name for s in registry.skills()),
    )


@dataclass(frozen=True, slots=True)
class OracleView:
    """Renderable publish-oracle status for one catalog record."""

    host_ok: bool
    skill_ok: bool | None
    stages: tuple[tuple[str, bool, str], ...]
    reliability_label: str

    @property
    def ok(self) -> bool:
        if not self.host_ok:
            return False
        return self.skill_ok is not False

    @property
    def pill_class(self) -> str:
        if self.ok:
            return "pill-ok"
        if not self.stages:
            return "pill-priv"
        if self.host_ok and self.skill_ok is None:
            return "pill-priv"
        return "pill-fail"

    @property
    def pill_text(self) -> str:
        if self.ok:
            return "check · freeze · smoke"
        if not self.stages:
            return "unscored"
        if not self.host_ok:
            failed = [
                name for name, passed, _ in self.stages if not passed and name in _HOST_STAGES
            ]
            if failed:
                return " · ".join(failed) + " fail"
            return "publish fail"
        if self.skill_ok is False:
            return f"smoke fail · {self.reliability_label}"
        return "unscored"


def _stage_rows(receipt: PublishReceipt | None) -> tuple[tuple[str, bool, str], ...]:
    if receipt is None:
        return ()
    rows: list[tuple[str, bool, str]] = []
    for stage in receipt.stages:
        name = str(getattr(stage, "name", "") or "")
        passed = bool(getattr(stage, "passed", False))
        summary = str(getattr(stage, "summary", "") or "")
        rows.append((name, passed, summary))
    return tuple(rows)


def _host_ok(receipt: PublishReceipt | None) -> bool:
    """Host product gate: check + freeze must pass (smoke is per-skill)."""
    if receipt is None:
        return False
    host_stages = [
        stage for stage in receipt.stages if str(getattr(stage, "name", "") or "") in _HOST_STAGES
    ]
    if not host_stages:
        return False
    return all(bool(getattr(stage, "passed", False)) for stage in host_stages)


def _skill_smoke_ok(skill_name: str | None) -> bool | None:
    if skill_name is None:
        return None
    if _receipt is None or _receipt.smoke is None:
        return None
    sliced = smoke_slice_for_skill(_receipt.smoke, skill_name)
    if sliced is None:
        return None
    return sliced.passed


def _reliability_label(skill_name: str | None) -> str:
    if skill_name is None or _scores is None:
        return "unscored"
    return _scores.get(skill_name).label


def oracle_for(record: ResolveRecord) -> OracleView:
    """Oracle pill data for a resolve record."""
    skill_name = RECORD_SKILL.get(record.name)
    host_ok = _host_ok(_receipt)
    skill_ok = _skill_smoke_ok(skill_name)
    if record.kind != "star":
        skill_ok = None
    return OracleView(
        host_ok=host_ok,
        skill_ok=skill_ok,
        stages=_stage_rows(_receipt),
        reliability_label=_reliability_label(skill_name),
    )


def oracle_ok_for_record(record: ResolveRecord) -> bool:
    """Whether the catalog row should show oracle-ok (used during catalog sync)."""
    view = oracle_for(record)
    if record.kind != "star":
        return view.host_ok
    return view.ok
