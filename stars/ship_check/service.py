from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from stars.npm_release.service import get as npm_get
from stars.pypi_release.service import get as pypi_get
from stars.source_watch.service import diff as source_diff

PYPI = frozenset({"httpx", "pydantic"})
NPM = frozenset({"zod", "@modelcontextprotocol/sdk"})


def run(
    package: str,
    source_digest: str = "",
    *,
    package_provider: Callable[[str], dict[str, object]] | None = None,
    source_provider: Callable[[str], dict[str, object]] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    if package not in PYPI | NPM:
        return {"error": "package_not_allowed", "package": package, "live_at_call": True}
    package_result = (package_provider or _package)(package)
    source_result = (
        source_provider or (lambda digest: source_diff("python-release-notes", digest))
    )(source_digest)
    utc = (clock or (lambda: datetime.now(UTC)))().isoformat()
    complete = "error" not in package_result and "error" not in source_result
    return {
        "constellation": "orrery/ship-check",
        "verdict": "ready_to_reason" if complete else "incomplete",
        "scope": "release metadata + fixed Python release notes + UTC evidence",
        "limitation": "This is not a deployment approval and has no side effects.",
        "components": [
            {
                "name": "orrery/pypi-release" if package in PYPI else "orrery/npm-release",
                "version": "0.1.0",
            },
            {"name": "orrery/source-watch", "version": "0.1.0"},
            {"name": "orrery/world-time", "version": "0.1.0"},
        ],
        "package": package_result,
        "source_watch": source_result,
        "utc": {"datetime": utc, "live_at_call": True},
        "live_at_call": True,
    }


def _package(package: str) -> dict[str, object]:
    return pypi_get(package) if package in PYPI else npm_get(package)
