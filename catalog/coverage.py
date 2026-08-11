"""Public allowlist coverage for agents (#221).

``GET /coverage/{star-or-family}`` returns machine-readable allowlist metadata
so agents can preflight before calling allowlist-gated stars. Agent Cards
(#217) link here via ``coverage_href``; this module does not define card schema.

Only **public** star allowlists are exposed. Private-namespace entries must
never appear here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final
from urllib.parse import quote

# Soft cap so huge future allowlists stay agent-scannable.
MAX_ENTRIES: Final = 50

# Stars / constellations with no machine-readable named allowlist yet (or whose
# gating is not a named public SKU map). Documented for agents and operators.
COVERAGE_GAPS: Final[tuple[str, ...]] = (
    "orrery/html-to-pdf",  # transform; no named target allowlist
    "orrery/csv-report",  # managed transform
    "orrery/image-transform",  # managed transform
    "orrery/world-time",  # fixed clock URLs, not a multi-entry SKU map
    "orrery/table-diff",  # caller-supplied snapshots
    "orrery/table-fresh",  # constellation over csv-url + table-diff
    "orrery/stale-proof",  # constellation over source-watch + world-time
    "orrery/board-memo",  # resumable pause → PDF seal dogfood (#154)
    "orrery/docs-migrate-to-mdx",  # frozen migration graph composer (#178)
)


@dataclass(frozen=True, slots=True)
class CoverageAllowlist:
    """One public star's allowlist projection."""

    star: str
    allowlist_kind: str
    check_param: str
    entries: tuple[str, ...]
    #: Optional secondary check (e.g. pep/rfc section).
    secondary_param: str | None = None
    #: membership(primary, secondary|None) → allowed
    membership: Callable[[str, str | None], bool] | None = None

    @property
    def aliases(self) -> frozenset[str]:
        short = self.star.partition("/")[2] or self.star
        return frozenset({self.star, short})


def _sorted_unique(values: object) -> tuple[str, ...]:
    items = list(values)  # type: ignore[arg-type]
    return tuple(sorted({str(item) for item in items}))


def _github_repos(targets: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    repos = {f"{owner}/{repo}" for owner, repo, *_rest in targets.values()}
    return tuple(sorted(repos))


def _build_registry() -> dict[str, CoverageAllowlist]:
    """Import public star contracts and project allowlists (lazy-friendly)."""
    from stars.cert_expiry.contract import HOSTS as CERT_HOSTS
    from stars.csv_url.contract import DATASET_URLS as CSV_DATASETS
    from stars.gh_file_at_ref.contract import TARGETS as GH_FILE_TARGETS
    from stars.gh_release_notes.contract import TARGETS as GH_RELEASE_TARGETS
    from stars.http_head.contract import TARGETS as HTTP_HEAD_TARGETS
    from stars.npm_release.contract import PACKAGE_PATHS as NPM_PACKAGES
    from stars.pep_section.contract import ALLOWED_SECTIONS as PEP_SECTIONS
    from stars.pep_section.contract import PEP_SOURCES
    from stars.pypi_release.contract import PACKAGES as PYPI_PACKAGES
    from stars.rfc_section.contract import ALLOWED_SECTIONS as RFC_SECTIONS
    from stars.rfc_section.contract import RFC_SOURCES
    from stars.row_lookup.contract import DATASET_URLS as ROW_DATASETS
    from stars.row_validate.contract import PROFILES as ROW_PROFILES
    from stars.ship_check.service import NPM as SHIP_NPM
    from stars.ship_check.service import PYPI as SHIP_PYPI
    from stars.source_watch.service import SOURCES as SOURCE_WATCH_SOURCES
    from stars.spdx_license.contract import LICENSE_IDS
    from stars.well_known.contract import DOCUMENTS as WELL_KNOWN_DOCS

    specs: list[CoverageAllowlist] = [
        CoverageAllowlist(
            star="orrery/http-head",
            allowlist_kind="named_target",
            check_param="target",
            entries=_sorted_unique(HTTP_HEAD_TARGETS),
        ),
        CoverageAllowlist(
            star="orrery/cert-expiry",
            allowlist_kind="named_host",
            check_param="host",
            entries=_sorted_unique(CERT_HOSTS),
            membership=lambda host, _sec: host in CERT_HOSTS
            or host in CERT_HOSTS.values(),
        ),
        CoverageAllowlist(
            star="orrery/well-known",
            allowlist_kind="named_document",
            check_param="document",
            entries=_sorted_unique(WELL_KNOWN_DOCS),
        ),
        CoverageAllowlist(
            star="orrery/pep-section",
            allowlist_kind="pep",
            check_param="pep",
            secondary_param="section",
            entries=_sorted_unique(PEP_SOURCES),
            membership=lambda pep, section: pep in PEP_SOURCES
            and (
                section is None
                or section == ""
                or section in PEP_SECTIONS.get(pep, frozenset())
            ),
        ),
        CoverageAllowlist(
            star="orrery/rfc-section",
            allowlist_kind="rfc",
            check_param="rfc",
            secondary_param="section",
            entries=_sorted_unique(RFC_SOURCES),
            membership=lambda rfc, section: rfc in RFC_SOURCES
            and (
                section is None
                or section == ""
                or section in RFC_SECTIONS.get(rfc, frozenset())
            ),
        ),
        CoverageAllowlist(
            star="orrery/spdx-license",
            allowlist_kind="spdx_id",
            check_param="license_id",
            entries=_sorted_unique(LICENSE_IDS),
        ),
        CoverageAllowlist(
            star="orrery/csv-url",
            allowlist_kind="named_dataset",
            check_param="dataset",
            entries=_sorted_unique(CSV_DATASETS),
        ),
        CoverageAllowlist(
            star="orrery/row-lookup",
            allowlist_kind="named_dataset",
            check_param="dataset",
            entries=_sorted_unique(ROW_DATASETS),
        ),
        CoverageAllowlist(
            star="orrery/row-validate",
            allowlist_kind="named_profile",
            check_param="profile",
            entries=_sorted_unique(ROW_PROFILES),
        ),
        CoverageAllowlist(
            star="orrery/pypi-release",
            allowlist_kind="pypi_package",
            check_param="package",
            entries=_sorted_unique(PYPI_PACKAGES),
        ),
        CoverageAllowlist(
            star="orrery/npm-release",
            allowlist_kind="npm_package",
            check_param="package",
            entries=_sorted_unique(NPM_PACKAGES),
        ),
        CoverageAllowlist(
            star="orrery/gh-file-at-ref",
            allowlist_kind="github_repo",
            check_param="repo",
            entries=_github_repos(GH_FILE_TARGETS),
        ),
        CoverageAllowlist(
            star="orrery/gh-release-notes",
            allowlist_kind="github_repo",
            check_param="repo",
            entries=_github_repos(GH_RELEASE_TARGETS),
        ),
        CoverageAllowlist(
            star="orrery/source-watch",
            allowlist_kind="named_source",
            check_param="source",
            entries=_sorted_unique(SOURCE_WATCH_SOURCES),
        ),
        CoverageAllowlist(
            star="orrery/ship-check",
            allowlist_kind="package",
            check_param="package",
            entries=_sorted_unique(SHIP_PYPI | SHIP_NPM),
        ),
    ]

    by_alias: dict[str, CoverageAllowlist] = {}
    for spec in specs:
        for alias in spec.aliases:
            if alias in by_alias and by_alias[alias].star != spec.star:
                msg = f"coverage alias collision: {alias!r}"
                raise RuntimeError(msg)
            by_alias[alias] = spec
    return by_alias


_REGISTRY: dict[str, CoverageAllowlist] | None = None


def coverage_registry() -> dict[str, CoverageAllowlist]:
    """Return the alias → allowlist map (built once)."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def list_coverage_stars() -> list[CoverageAllowlist]:
    """Unique public coverage specs, sorted by star name."""
    seen: dict[str, CoverageAllowlist] = {}
    for spec in coverage_registry().values():
        seen[spec.star] = spec
    return [seen[name] for name in sorted(seen)]


def resolve_coverage(star_or_family: str) -> CoverageAllowlist | None:
    """Resolve a star id, short name, or alias to a coverage spec."""
    key = (star_or_family or "").strip().strip("/")
    if not key:
        return None
    registry = coverage_registry()
    if key in registry:
        return registry[key]
    if not key.startswith("orrery/") and f"orrery/{key}" in registry:
        return registry[f"orrery/{key}"]
    return None


def coverage_href(star_or_family: str) -> str:
    """Path agents / Agent Cards should use as ``coverage_href`` (#217)."""
    short = star_or_family.partition("/")[2] or star_or_family
    return f"/coverage/{short}"


def _check_href(spec: CoverageAllowlist) -> str:
    short = spec.star.partition("/")[2] or spec.star
    sample = "owner/name" if spec.check_param == "repo" else "value"
    href = f"/coverage/{short}/check?{spec.check_param}={quote(sample, safe='/')}"
    if spec.secondary_param:
        href += f"&{spec.secondary_param}=value"
    return href


def describe_coverage(star_or_family: str) -> dict[str, object] | None:
    """Public coverage metadata for one star, or ``None`` if unknown."""
    spec = resolve_coverage(star_or_family)
    if spec is None:
        return None
    total = len(spec.entries)
    truncated = total > MAX_ENTRIES
    entries = list(spec.entries[:MAX_ENTRIES])
    return {
        "star": spec.star,
        "allowlist_kind": spec.allowlist_kind,
        "entries": entries,
        "entries_truncated": truncated,
        "total_count": total,
        "coverage_href": coverage_href(spec.star),
        "check": {
            "href": _check_href(spec),
            "param": spec.check_param,
            "returns": {"allowed": True, "reason": None},
        },
        "note": (
            "Agent Cards link here via coverage_href once #217 lands. "
            "Private-namespace allowlists are never exposed."
        ),
    }


def check_coverage(
    star_or_family: str,
    *,
    params: Mapping[str, str],
) -> dict[str, object]:
    """Return ``{allowed, reason}`` for a coverage membership query.

    Unknown stars → ``allowed=False`` with ``reason=unknown_star``.
    Missing primary query param → ``allowed=False`` with ``reason=missing_param``.
    """
    spec = resolve_coverage(star_or_family)
    if spec is None:
        return {"allowed": False, "reason": "unknown_star", "star": star_or_family}

    raw = params.get(spec.check_param)
    # SPDX agents may send ``id`` as a shorthand.
    if raw is None and spec.check_param == "license_id":
        raw = params.get("id")
    if raw is None or not str(raw).strip():
        return {
            "allowed": False,
            "reason": "missing_param",
            "star": spec.star,
            "param": spec.check_param,
        }

    primary = str(raw).strip()
    secondary: str | None = None
    if spec.secondary_param:
        sec_raw = params.get(spec.secondary_param)
        secondary = str(sec_raw).strip() if sec_raw is not None else None

    if spec.membership is not None:
        allowed = bool(spec.membership(primary, secondary))
    else:
        allowed = primary in spec.entries

    if allowed:
        return {"allowed": True, "reason": None, "star": spec.star}
    return {
        "allowed": False,
        "reason": "not_allowlisted",
        "star": spec.star,
        "allowlist_kind": spec.allowlist_kind,
    }


def coverage_index() -> dict[str, object]:
    """List all public allowlist-gated stars and known gaps."""
    stars = []
    for spec in list_coverage_stars():
        stars.append(
            {
                "star": spec.star,
                "allowlist_kind": spec.allowlist_kind,
                "total_count": len(spec.entries),
                "href": coverage_href(spec.star),
                "check_param": spec.check_param,
            }
        )
    return {
        "stars": stars,
        "count": len(stars),
        "gaps": list(COVERAGE_GAPS),
        "note": (
            "Gaps are public stars without a named machine-readable allowlist "
            "(transforms, fixed clocks, or constellation composers)."
        ),
    }
