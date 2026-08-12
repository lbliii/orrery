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
    assert payload["allowlist_kind"] == "named_target"
    assert payload["entries_truncated"] is False
    assert payload["total_count"] == len(payload["entries"])
    assert "orrery-readme" in payload["entries"]
    check = payload["check"]
    assert isinstance(check, dict)
    assert check["href"].startswith("/coverage/gh-file-at-ref/check?target=")
    assert check["param"] == "target"
    assert check["returns"] == {"allowed": True, "reason": None}
    assert payload["coverage_href"] == coverage_href("orrery/gh-file-at-ref")


def test_check_gh_file_at_ref_target_membership() -> None:
    ok = check_coverage("gh-file-at-ref", params={"target": "orrery-readme"})
    assert ok == {
        "allowed": True,
        "reason": None,
        "star": "orrery/gh-file-at-ref",
    }
    denied = check_coverage("gh-file-at-ref", params={"target": "not-a-real-target"})
    assert denied["allowed"] is False
    assert denied["reason"] == "not_allowlisted"
    assert denied["catalog_href"] == "/coverage/gh-file-at-ref"
    allowed_values = denied.get("allowed_values")
    assert isinstance(allowed_values, list) and allowed_values
    assert "orrery-readme" in allowed_values


@pytest.mark.issue(344)
def test_gh_file_at_ref_coverage_allowed_implies_runtime_target() -> None:
    """Coverage uses runtime param; documented corpus args pass the allowlist."""
    from stars.gh_file_at_ref.contract import TARGETS
    from stars.gh_file_at_ref.corpus import CORPUS
    from stars.gh_file_at_ref.service import get

    example = CORPUS[0].arguments
    target = str(example["target"])
    ref = str(example["ref"])
    ok = check_coverage("gh-file-at-ref", params={"target": target})
    assert ok["allowed"] is True
    assert target in TARGETS

    source = json.dumps(
        {"content": "IyBP\nc nJlcnk=\n".replace(" ", ""), "sha": "blob", "type": "file"}
    ).encode()

    result = get(
        target=target,
        ref=ref,
        fetch=lambda url, **_: (url, 200, {}, source),
    )
    assert "error" not in result
    assert result["target"] == target


@pytest.mark.issue(340)
def test_denied_coverage_check_includes_remediation() -> None:
    """Denied checks expose allowed_values and/or catalog_href (#340)."""
    denied = check_coverage("npm-release", params={"package": "express"})
    assert denied["allowed"] is False
    assert denied["reason"] == "not_allowlisted"
    assert denied.get("catalog_href") == "/coverage/npm-release"
    allowed_values = denied.get("allowed_values")
    assert isinstance(allowed_values, list) and allowed_values
    assert "zod" in allowed_values


@pytest.mark.issue(340)
def test_describe_table_fresh_gap_links_upstream() -> None:
    payload = describe_coverage("table-fresh")
    assert payload is not None
    assert payload["kind"] == "coverage_gap"
    assert payload["star"] == "orrery/table-fresh"
    upstream = payload["upstream_allowlists"]
    assert isinstance(upstream, list) and upstream
    csv = next(item for item in upstream if item["star"] == "orrery/csv-url")
    assert csv["catalog_href"] == "/coverage/csv-url"
    assert csv["check_param"] == "dataset"
    assert "flights-airport" in csv["allowed_values"]


@pytest.mark.issue(340)
def test_describe_stale_proof_gap_links_source_watch() -> None:
    payload = describe_coverage("stale-proof")
    assert payload is not None
    upstream = payload["upstream_allowlists"]
    watch = next(item for item in upstream if item["star"] == "orrery/source-watch")
    assert watch["catalog_href"] == "/coverage/source-watch"
    assert isinstance(watch.get("allowed_values"), list)


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
        assert json.loads(meta.text)["allowlist_kind"] == "named_target"

        allowed = await client.get(
            "/coverage/gh-file-at-ref/check?target=orrery-readme",
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
        denied_body = json.loads(denied.text)
        assert denied_body["allowed"] is False
        assert denied_body.get("catalog_href") == "/coverage/http-head"
        assert isinstance(denied_body.get("allowed_values"), list)

        gap = await client.get("/coverage/table-fresh", headers=HOST)
        assert gap.status == 200
        gap_body = json.loads(gap.text)
        assert gap_body["kind"] == "coverage_gap"
        assert any(
            u["star"] == "orrery/csv-url" for u in gap_body["upstream_allowlists"]
        )

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
                        "target": "flask",
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


@pytest.mark.issue(340)
@pytest.mark.asyncio
async def test_mcp_coverage_check_denied_includes_remediation(example_app) -> None:
    async with TestClient(example_app) as client:
        called = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": _modern_mcp_params(
                    name="coverage_check",
                    arguments={
                        "star": "npm-release",
                        "package": "express",
                    },
                ),
            },
            headers=_modern_mcp_headers("tools/call", "coverage_check"),
        )
        assert called.status == 200
        text = json.loads(called.text)["result"]["content"][0]["text"]
        assert "not_allowlisted" in text
        assert "catalog_href" in text
        assert "/coverage/npm-release" in text
        assert "allowed_values" in text
        assert "zod" in text