"""Source Watch Star-package contract tests (#52)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from stars.source_watch import ANSWER_MAX_CHARS, answer, diff, observe, service, tool_schemas
from stars.source_watch.fixtures import fixture_environment
from stars.source_watch.skill import build_skill


@pytest.mark.issue(52)
class TestSourceWatchPackage:
    def test_manifest_declares_direct_endpoint_and_publish_contract(self) -> None:
        manifest_path = Path(__file__).parents[2] / "stars" / "source_watch" / "star.toml"
        manifest = tomllib.loads(manifest_path.read_text())

        assert manifest["star"]["name"] == "orrery/source-watch"
        assert manifest["star"]["direct_mcp_path"] == "/stars/source-watch/mcp"
        assert manifest["runtime"]["skill_factory"] == "stars.source_watch.skill:build_skill"
        assert manifest["policy"]["freshness"] == "live_at_call"
        assert manifest["publish"]["corpus"] == "stars.source_watch.corpus:CORPUS"

    def test_framework_free_service_observes_diffs_and_answers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service._history.clear()
        monkeypatch.setenv(
            "ORRERY_SOURCE_WATCH_FIXTURES",
            fixture_environment("Python 3.14 security guidance.")["ORRERY_SOURCE_WATCH_FIXTURES"],
        )
        first = observe()
        same = diff(since_digest=str(first["normalized_sha256"]))
        result = answer("What security guidance?", max_chars=80)

        assert first["status"] == "new"
        assert same["status"] == "unchanged"
        assert result["extractive"] is True
        assert "security" in str(result["answer"]).lower()
        assert result["live_at_call"] is True

    def test_contract_exposes_canonical_answer_schema(self) -> None:
        schemas = tool_schemas()

        assert set(schemas) == {"observe", "diff", "answer"}
        answer_schema = schemas["answer"]["inputSchema"]
        assert answer_schema["required"] == ["question"]
        assert answer_schema["properties"]["max_chars"]["maximum"] == ANSWER_MAX_CHARS

    def test_chirp_adapter_uses_canonical_local_answer_name(self) -> None:
        skill = build_skill()
        names = {pending.name for pending in skill._pending}

        assert names == {"observe", "diff", "answer"}
        assert "source_watch_answer" not in names
