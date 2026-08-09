"""Publish-oracle status for resolve rows and star pages (#34).

Reads the host :class:`~chirp.skill.publish.PublishReceipt` (check → freeze →
smoke) and per-skill :class:`~chirp.skill.console.ReliabilityScore` values so
public oracle pills agree with ``/console``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chirp.skill.console import ReliabilityStore
    from chirp.skill.publish import PublishReceipt

    from catalog.models import ResolveRecord

#: Resolve catalog name → mounted dogfood skill name (public callable stars).
RECORD_SKILL: dict[str, str] = {
    "orrery/html-to-pdf": "html-to-pdf",
    "orrery/world-time": "world-time",
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
    "run": "launch-gate",
    "status": "launch-gate",
    "explain_policy": "launch-gate",
}

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
        if self.skill_ok is False:
            return False
        return True

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
            failed = [name for name, passed, _ in self.stages if not passed]
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
    if receipt is None:
        return False
    return bool(receipt.passed)


def _skill_smoke_ok(skill_name: str | None) -> bool | None:
    if skill_name is None:
        return None
    if _receipt is None or _receipt.smoke is None:
        return None
    results = _receipt.smoke.results
    relevant = [r for r in results if TOOL_SKILL.get(r.tool) == skill_name]
    if not relevant:
        return None
    return all(r.verdict.passed for r in relevant)


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
