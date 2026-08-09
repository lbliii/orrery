"""Direct-endpoint package tests for the pre-existing dogfood Stars (#52)."""

from __future__ import annotations

import base64
import hashlib
import tomllib
from pathlib import Path

import pytest

from artifacts.storage import InMemoryObjectStorage
from stars.html_to_pdf import convert, health
from stars.html_to_pdf.artifacts import (
    DurablePdfArtifactService,
    InMemoryPdfArtifactRepository,
    configure_pdf_artifacts,
    get_pdf_artifacts,
)
from stars.html_to_pdf.contract import tool_schemas as pdf_tool_schemas
from stars.html_to_pdf.skill import build_skill as build_pdf_skill
from stars.world_time import answer, fetch
from stars.world_time.contract import tool_schemas as world_time_tool_schemas
from stars.world_time.fixtures import fixture_environment
from stars.world_time.skill import build_skill as build_world_time_skill


@pytest.mark.issue(52)
class TestExistingStarPackages:
    @pytest.mark.parametrize(
        ("package", "name", "path", "factory"),
        [
            (
                "html_to_pdf",
                "orrery/html-to-pdf",
                "/stars/html-to-pdf/mcp",
                "stars.html_to_pdf.skill:build_skill",
            ),
            (
                "world_time",
                "orrery/world-time",
                "/stars/world-time/mcp",
                "stars.world_time.skill:build_skill",
            ),
        ],
    )
    def test_manifest_declares_direct_endpoint_and_publish_contract(
        self, package: str, name: str, path: str, factory: str
    ) -> None:
        manifest_path = Path(__file__).parents[2] / "stars" / package / "star.toml"
        manifest = tomllib.loads(manifest_path.read_text())

        assert manifest["star"]["name"] == name
        assert manifest["star"]["direct_mcp_path"] == path
        assert manifest["runtime"]["skill_factory"] == factory
        assert manifest["publish"]["corpus"].endswith(".corpus:CORPUS")

    def test_html_to_pdf_framework_free_service_and_adapter(self) -> None:
        configure_pdf_artifacts(
            DurablePdfArtifactService(InMemoryPdfArtifactRepository(), InMemoryObjectStorage())
        )
        result = convert("<h1>Orrery</h1><p>Release evidence</p>")
        pdf = base64.b64decode(result["artifact_base64"])

        assert pdf.startswith(b"%PDF-")
        assert result["sha256"] == hashlib.sha256(pdf).hexdigest()
        assert result["byte_length"] == len(pdf)
        assert result["page_count"] == 1
        assert result["content_type"] == "application/pdf"
        assert b"<h1>" not in pdf
        assert b"Orrery" in pdf
        assert health() == {
            "status": "ok",
            "skill": "html-to-pdf",
            "artifact_delivery": "durable",
        }
        assert set(pdf_tool_schemas()) == {"convert", "submit", "result", "health"}
        skill = build_pdf_skill()
        assert {pending.name for pending in skill._pending} == {
            "convert",
            "submit",
            "result",
            "health",
        }
        envelope = next(pending for pending in skill._pending if pending.name == "convert").handler(
            html="<p>Download me</p>"
        )
        payload = envelope.payload
        artifact_id = str(payload["artifact_url"]).rsplit("/", maxsplit=1)[-1]
        delivered = get_pdf_artifacts().download(artifact_id)
        assert delivered is not None
        artifact, data = delivered
        assert payload["sha256"] == f"sha256:{artifact.sha256}"
        assert data.startswith(b"%PDF-")

    def test_world_time_framework_free_service_and_adapter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        environment = fixture_environment()
        monkeypatch.setenv("ORRERY_WORLD_TIME_JSON", environment["ORRERY_WORLD_TIME_JSON"])

        result = fetch()
        assert result["datetime"] == "2026-08-08T12:34:56Z"
        assert result["live_at_call"] is True
        assert answer()["answer"] == "UTC now is 2026-08-08T12:34:56Z"
        assert set(world_time_tool_schemas()) == {"fetch", "get", "answer"}
        assert {pending.name for pending in build_world_time_skill()._pending} == {
            "fetch",
            "get",
            "answer",
        }
