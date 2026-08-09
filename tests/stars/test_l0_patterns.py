"""L0 allowlist-negative + contract patterns for dogfood stars (#116)."""

from __future__ import annotations

import pytest

from stars.html_to_pdf import convert, health
from stars.html_to_pdf import tool_schemas as pdf_schemas
from stars.source_watch import observe
from stars.source_watch import tool_schemas as source_watch_schemas
from stars.source_watch.service import SOURCES
from stars.world_time import answer, fetch
from stars.world_time import tool_schemas as world_time_schemas
from stars.world_time.contract import WORLD_TIME_URL
from stars.world_time.fixtures import fixture_environment
from tests.stars.helpers import (
    assert_allowlist_rejects,
    assert_egress_covers_url,
    assert_manifest_publish_corpus,
    assert_payload_keys,
    assert_tool_schema_keys,
    load_star_manifest,
)


@pytest.mark.issue(116)
class TestL0SourceWatch:
    def test_out_of_allowlist_source_fails_loud(self) -> None:
        assert "https://example.com/not-a-source" not in SOURCES
        result = assert_allowlist_rejects(observe, "https://example.com/not-a-source")
        assert result["live_at_call"] is True

    def test_contract_tools_and_egress_cover_canonical_source(self) -> None:
        manifest = load_star_manifest("source_watch")
        assert_tool_schema_keys(source_watch_schemas(), {"observe", "diff", "answer"})
        assert_egress_covers_url(
            manifest["policy"]["allowed_egress"],
            SOURCES["python-release-notes"],
        )
        assert_manifest_publish_corpus("source_watch")


@pytest.mark.issue(116)
class TestL0WorldTime:
    def test_egress_allowlist_covers_contract_clock_url(self) -> None:
        """World Time has no user-supplied URL; L0 is fixed-egress + contract hold."""
        manifest = load_star_manifest("world_time")
        egress = manifest["policy"]["allowed_egress"]
        assert egress, "live stars must declare allowed_egress"
        assert_egress_covers_url(egress, WORLD_TIME_URL)
        assert_tool_schema_keys(world_time_schemas(), {"fetch", "get", "answer"})
        assert_manifest_publish_corpus("world_time")

    def test_fixture_happy_path_payload_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        environment = fixture_environment()
        monkeypatch.setenv("ORRERY_WORLD_TIME_JSON", environment["ORRERY_WORLD_TIME_JSON"])
        payload = fetch()
        assert_payload_keys(
            payload,
            ("timezone", "datetime", "source", "live_at_call", "clone_warning"),
        )
        answered = answer()
        assert_payload_keys(answered, ("answer", "live_at_call", "clone_warning"))


@pytest.mark.issue(116)
class TestL0HtmlToPdf:
    def test_contract_types_and_empty_egress(self) -> None:
        """Transform faucet: no egress allowlist; contract types fail loud."""
        manifest = load_star_manifest("html_to_pdf")
        assert manifest["policy"]["allowed_egress"] == []
        assert_tool_schema_keys(pdf_schemas(), {"convert", "health", "submit", "result"})
        assert_manifest_publish_corpus("html_to_pdf")
        with pytest.raises(TypeError, match="html must be a string"):
            convert(None)  # type: ignore[arg-type]

    def test_happy_path_payload_keys(self) -> None:
        payload = convert("<p>L0</p>")
        assert_payload_keys(
            payload,
            ("artifact_base64", "sha256", "byte_length", "page_count", "content_type"),
        )
        assert health()["status"] == "ok"
