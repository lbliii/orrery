from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.well_known.contract import tool_schemas
from stars.well_known.service import read
from stars.well_known.skill import build_skill


def test_bounded_llms_slice_with_injected_local_provider() -> None:
    result = read(
        "orrery-llms",
        provider=lambda _document, _url: b"# Orrery\n",
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert result["canonical_url"] == "https://orrery.lol/llms.txt"
    assert result["text_slice"] == "# Orrery\n" and result["content_digest"].startswith("sha256:")
    assert result["source"] == {
        "publisher": "Orrery",
        "document_type": "text",
        "provider": "local-authoritative",
    }


def test_card_parse_and_policy_rejections() -> None:
    card = b'{"serverInfo":{"name":"orrery","version":"1"},"transport":{"endpoint":"https://orrery.lol/mcp"}}'
    result = read("orrery-mcp-server-card", provider=lambda _document, _url: card)
    assert result["mcp_card"]["endpoint"] == "https://orrery.lol/mcp"
    assert read("https://evil.example/")["error"] == "document_not_allowed"
    assert (
        read(
            "orrery-llms", provider=lambda _document, _url: (_ for _ in ()).throw(OSError("down"))
        )["error"]
        == "publication_unavailable"
    )
    assert (
        read("orrery-llms", provider=lambda _document, _url: b"x" * (64 * 1024 + 1))["error"]
        == "publication_too_large"
    )


def test_default_provider_projects_local_discovery_without_http(monkeypatch) -> None:
    monkeypatch.setenv("ORRERY_PUBLIC_ORIGIN", "https://example.test")
    llms, card = read("orrery-llms"), read("orrery-mcp-server-card")
    assert llms["canonical_url"] == "https://orrery.lol/llms.txt"
    assert "https://example.test/mcp" in llms["text_slice"]
    assert card["mcp_card"]["endpoint"] == "https://example.test/mcp"


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"read"}
    assert {item.name for item in build_skill()._pending} == {"read"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/well-known"
        ).direct_mcp_path
        == "/stars/well-known/mcp"
    )
