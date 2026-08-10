"""Coverage API — public allowlist preflight for agents (#221)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient
from test_app import _modern_mcp_headers, _modern_mcp_params

from catalog.coverage import (
    COVERAGE_GAPS,
    MAX_ENTRIES,
    check_coverage,
    coverage_href,
    coverage_index,
    describe_coverage,
    list_coverage_stars,
    resolve_coverage,
)

HOST = {"Host": "orrery.lol"}


def test_registry_covers_allowlist_gated_stars() -> None:
    stars = {spec.star for spec in list_coverage_stars()}
    expected = {
        "orrery/http-head",
        "orrery/cert-expiry",
        "orrery/well-known",
        "orrery/pep-section",
        "orrery/rfc-section",
        "orrery/spdx-license",
        "orrery/csv-url",
        "orrery/row-lookup",
        "orrery/row-validate",
        "orrery/pypi-release",
        "orrery/npm-release",
        "orrery/gh-file-at-ref",
        "orrery/gh-release-notes",
        "orrery/source-watch",
        "orrery/ship-check",
    }
    assert expected <= stars
    # Gaps stay out of the machine-readable registry.
    assert not (set(COVERAGE_GAPS) & stars)


def test_resolve_accepts_short_and_namespaced_ids() -> None:
    short = resolve_coverage("gh-file-at-ref")
    full = resolve_coverage("orrery/gh-file-at-ref")
    assert short is not None and full is not None
    assert short.star == full.star == "orrery/gh-file-at-ref"
    assert resolve_coverage("no-such-star") is None


def test_describe_gh_file_at_ref_shape() -> None:
    payload = describe_coverage("gh-file-at-ref")
    assert payload is not None
    assert payload["star"] == "orrery/gh-file-at-ref"
    assert payload["allowlist_kind"] == "github_repo"
    assert payload["entries_truncated"] is False
    assert payload["total_count"] == len(payload["entries"])
    assert "lbliii/orrery" in payload["entries"]
    check = payload["check"]
    assert isinstance(check, dict)
    assert check["href"].startswith("/coverage/gh-file-at-ref/check?repo=")
    assert check["returns"] == {"allowed": True, "reason": None}
    assert payload["coverage_href"] == coverage_href("orrery/gh-file-at-ref")


def test_check_github_repo_membership() -> None:
    ok = check_coverage("gh-file-at-ref", params={"repo": "lbliii/orrery"})
    assert ok == {
        "allowed": True,
        "reason": None,
        "star": "orrery/gh-file-at-ref",
    }
    denied = check_coverage("gh-file-at-ref", params={"repo": "torvalds/linux"})
    assert denied["allowed"] is False
    assert denied["reason"] == "not_allowlisted"


def test_check_package_and_pep_section() -> None:
    assert check_coverage("pypi-release", params={"package": "httpx"})["allowed"] is True
    assert check_coverage("npm-release", params={"package": "zod"})["allowed"] is True
    pep_ok = check_coverage(
        "pep-section",
        params={"pep": "8", "section": "Introduction"},
    )
    assert pep_ok["allowed"] is True
    pep_bad = check_coverage(
        "pep-section",
        params={"pep": "8", "section": "Not A Real Section"},
    )
    assert pep_bad["allowed"] is False
    # Primary-only check still works when section omitted.
    assert check_coverage("pep-section", params={"pep": "8"})["allowed"] is True


def test_check_missing_param_and_unknown_star() -> None:
    missing = check_coverage("spdx-license", params={})
    assert missing["allowed"] is False
    assert missing["reason"] == "missing_param"
    unknown = check_coverage("acme/secret-star", params={"repo": "x/y"})
    assert unknown["allowed"] is False
    assert unknown["reason"] == "unknown_star"


def test_no_private_namespace_leak_in_index() -> None:
    index = coverage_index()
    blob = str(index).lower()
    assert "acme/" not in blob
    assert "secret" not in blob
    for entry in index["stars"]:
        assert str(entry["star"]).startswith("orrery/")


def test_entries_truncation_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from catalog import coverage as coverage_mod
    from catalog.coverage import CoverageAllowlist

    huge = tuple(f"id-{i}" for i in range(MAX_ENTRIES + 5))
    fake = CoverageAllowlist(
        star="orrery/fake-truncation",
        allowlist_kind="named_target",
        check_param="target",
        entries=huge,
    )
    monkeypatch.setitem(coverage_mod.coverage_registry(), "fake-truncation", fake)
    monkeypatch.setitem(
        coverage_mod.coverage_registry(),
        "orrery/fake-truncation",
        fake,
    )
    payload = describe_coverage("fake-truncation")
    assert payload is not None
    assert payload["entries_truncated"] is True
    assert payload["total_count"] == MAX_ENTRIES + 5
    assert len(payload["entries"]) == MAX_ENTRIES


@pytest.mark.asyncio
async def test_http_coverage_routes(example_app) -> None:
    async with TestClient(example_app) as client:
        index = await client.get("/coverage", headers=HOST)
        assert index.status == 200
        body = json.loads(index.text)
        assert body["count"] >= 15
        assert any(s["star"] == "orrery/gh-file-at-ref" for s in body["stars"])

        meta = await client.get("/coverage/gh-file-at-ref", headers=HOST)
        assert meta.status == 200
        assert json.loads(meta.text)["allowlist_kind"] == "github_repo"

        allowed = await client.get(
            "/coverage/gh-file-at-ref/check?repo=lbliii/orrery",
            headers=HOST,
        )
        assert allowed.status == 200
        assert json.loads(allowed.text) == {
            "allowed": True,
            "reason": None,
            "star": "orrery/gh-file-at-ref",
        }

        denied = await client.get(
            "/coverage/http-head/check?target=not-a-real-target",
            headers=HOST,
        )
        assert denied.status == 200
        assert json.loads(denied.text)["allowed"] is False

        missing = await client.get("/coverage/nope-star", headers=HOST)
        assert missing.status == 404


@pytest.mark.asyncio
async def test_mcp_coverage_check_tool(example_app) -> None:
    async with TestClient(example_app) as client:
        listed = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": _modern_mcp_params(),
            },
            headers=_modern_mcp_headers("tools/list"),
        )
        assert listed.status == 200
        tools = {t["name"] for t in json.loads(listed.text)["result"]["tools"]}
        assert "coverage_check" in tools

        called = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": _modern_mcp_params(
                    name="coverage_check",
                    arguments={
                        "star": "gh-release-notes",
                        "repo": "pallets/flask",
                    },
                ),
            },
            headers=_modern_mcp_headers("tools/call", "coverage_check"),
        )
        assert called.status == 200
        text = json.loads(called.text)["result"]["content"][0]["text"]
        assert "orrery/gh-release-notes" in text
        assert "allowed" in text
        assert "True" in text or "true" in text