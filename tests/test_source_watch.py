"""Source Watch v1 — allowlisted, live-at-call source evidence (#51)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient
from test_app import _modern_mcp_headers, _modern_mcp_params


def _fixture(document: str) -> str:
    return json.dumps({"python-release-notes": document})


@pytest.mark.issue(51)
class TestSourceWatch:
    def test_observe_tracks_raw_and_normalized_digest_history(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from stars.source_watch import service as source_watch

        source_watch._history.clear()
        monkeypatch.setenv("ORRERY_SOURCE_WATCH_FIXTURES", _fixture("Python 3.14\r\n"))
        first = source_watch.observe("python-release-notes")
        second = source_watch.observe("python-release-notes")

        assert first["status"] == "new"
        assert second["status"] == "unchanged"
        assert first["canonical_url"] == "https://docs.python.org/3/whatsnew/3.14.html"
        assert first["raw_sha256"].startswith("sha256:")
        assert first["normalized_sha256"].startswith("sha256:")
        assert first["live_at_call"] is True

        monkeypatch.setenv("ORRERY_SOURCE_WATCH_FIXTURES", _fixture("Python 3.14.1\n"))
        changed = source_watch.observe("python-release-notes")
        assert changed["status"] == "changed"

    def test_diff_fetches_now_and_compares_a_known_observation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from stars.source_watch import service as source_watch

        source_watch._history.clear()
        monkeypatch.setenv("ORRERY_SOURCE_WATCH_FIXTURES", _fixture("Python 3.14.0 notes"))
        prior = source_watch.observe()
        same = source_watch.diff(since_digest=str(prior["normalized_sha256"]))
        assert same["status"] == "unchanged"
        assert same["live_at_call"] is True
        assert same["evidence"]["normalized_sha256"] == prior["normalized_sha256"]

        monkeypatch.setenv("ORRERY_SOURCE_WATCH_FIXTURES", _fixture("Python 3.14.1 security notes"))
        changed = source_watch.diff(since_digest=str(prior["normalized_sha256"]))
        assert changed["status"] == "changed"
        assert changed["current_digest"] != prior["normalized_sha256"]

    def test_answer_is_bounded_extractive_evidence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from stars.source_watch import service as source_watch

        source_watch._history.clear()
        monkeypatch.setenv(
            "ORRERY_SOURCE_WATCH_FIXTURES",
            _fixture("Python 3.14 release notes include security guidance. " * 20),
        )
        result = source_watch.answer("What security guidance is included?", max_chars=80)
        assert result["extractive"] is True
        assert len(str(result["answer"])) <= 81
        assert "security" in str(result["answer"]).lower()
        assert result["evidence"]["canonical_url"].startswith("https://docs.python.org/")
        assert str(result["source_digest"]).startswith("sha256:")
        assert result["live_at_call"] is True

    def test_rejects_an_unallowlisted_source(self) -> None:
        from stars.source_watch.service import observe
        from tests.stars.helpers import assert_allowlist_rejects

        result = assert_allowlist_rejects(observe, "https://example.com/not-a-source")
        assert result["live_at_call"] is True

    def test_signed_source_watch_receipt_verifies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORRERY_SOURCE_WATCH_FIXTURES", _fixture("Python 3.14 security notes"))
        from dogfood import signed_source_watch_receipt, verify_receipt

        receipt, verified = signed_source_watch_receipt()
        assert verified is True
        assert receipt["skill"] == "source-watch"
        assert receipt["tool"] == "observe"
        assert receipt["payload"]["live_at_call"] is True
        assert receipt["payload"]["normalized_sha256"].startswith("sha256:")
        assert verify_receipt(receipt) is True

    async def test_mcp_tools_expose_source_watch_evidence(self, example_app) -> None:
        async with TestClient(example_app) as client:
            listed = await client.post(
                "/mcp/dogfood",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 51,
                    "params": _modern_mcp_params(),
                },
                headers=_modern_mcp_headers("tools/list"),
            )
            names = {tool["name"] for tool in json.loads(listed.text)["result"]["tools"]}
            assert {"observe", "diff", "source_watch_answer"} <= names

            observed = await client.post(
                "/mcp/dogfood",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 52,
                    "params": _modern_mcp_params(
                        name="observe", arguments={"source": "python-release-notes"}
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "observe"),
            )
            text = json.loads(observed.text)["result"]["content"][0]["text"]
            assert "source-watch" in text
            assert "normalized_sha256" in text
            assert "live_at_call" in text

            answered = await client.post(
                "/mcp/dogfood",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 53,
                    "params": _modern_mcp_params(
                        name="source_watch_answer",
                        arguments={
                            "source": "python-release-notes",
                            "question": "What guidance is current?",
                            "max_chars": 120,
                        },
                    ),
                },
                headers=_modern_mcp_headers("tools/call", "source_watch_answer"),
            )
            answer_text = json.loads(answered.text)["result"]["content"][0]["text"]
            assert "evidence" in answer_text
            assert "https://docs.python.org/3/whatsnew/3.14.html" in answer_text

    def test_catalog_exposes_source_watch(self, example_app) -> None:
        from catalog import CATALOG

        record = CATALOG.resolve("orrery/source-watch")
        assert record is not None
        assert record.endpoint == "mcp://orrery.lol/stars/source-watch/mcp"
        assert record.tools == ("observe", "diff", "answer")
        hits = CATALOG.match("official release notes", node="public")
        assert any(hit.name == "orrery/source-watch" for hit in hits)
