from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.well_known.contract import tool_schemas
from stars.well_known.service import read
from stars.well_known.skill import build_skill


def test_bounded_llms_slice_with_injected_transport() -> None:
    result = read(
        "orrery-llms",
        transport=lambda url, **_: (url, 200, {}, b"# Orrery\n"),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert result["canonical_url"] == "https://orrery.lol/llms.txt"
    assert result["text_slice"] == "# Orrery\n" and result["content_digest"].startswith("sha256:")
    assert result["source"]["document_type"] == "text"


def test_card_parse_and_policy_rejections() -> None:
    card = b'{"serverInfo":{"name":"orrery","version":"1"},"transport":{"endpoint":"https://orrery.lol/mcp"}}'
    result = read("orrery-mcp-server-card", transport=lambda url, **_: (url, 200, {}, card))
    assert result["mcp_card"]["endpoint"] == "https://orrery.lol/mcp"
    assert read("https://evil.example/")["error"] == "document_not_allowed"
    assert (
        read(
            "orrery-llms",
            transport=lambda *_args, **_kwargs: ("https://evil.example/", 302, {}, b""),
        )["error"]
        == "redirect_not_allowed"
    )
    assert (
        read("orrery-llms", transport=lambda url, **_: (url, 200, {}, b"x" * (64 * 1024 + 1)))[
            "error"
        ]
        == "upstream_too_large"
    )


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"read"}
    assert {item.name for item in build_skill()._pending} == {"read"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/well-known"
        ).direct_mcp_path
        == "/stars/well-known/mcp"
    )
