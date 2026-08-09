from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.rfc_section.contract import tool_schemas
from stars.rfc_section.service import get
from stars.rfc_section.skill import build_skill

SOURCE = b"RFC 9110\n\n3.1. Message\nThis is the selected text.\n\n4. Other\nNext section.\n"
TOC_AND_BODY = b"""RFC 9110

Contents
3.1. Resources .................................................. 10
4. Semantics ..................................................... 20

\f
3.1. Resources
The body explains resource identification, not a table of contents entry.

4. Semantics
The body explains HTTP semantics.
"""
URL = "https://www.rfc-editor.org/rfc/rfc9110.txt"


def test_named_section_uses_injected_canonical_source_and_digests() -> None:
    result = get(
        "9110",
        "3.1",
        fetch=lambda url, **_: (url, 200, {}, SOURCE),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert (
        result["canonical_url"] == URL
        and result["text_slice"] == "3.1. Message\nThis is the selected text."
    )
    assert result["source_digest"].startswith("sha256:") and result["slice_digest"].startswith(
        "sha256:"
    )
    assert result["source"] == {"publisher": "RFC Editor", "format": "text/plain"}


def test_unknown_rfc_or_section_never_fetches_and_missing_section_is_loud() -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert get("9999", "1", fetch=fail)["error"] == "rfc_or_section_not_allowed"
    assert get("9110", "9", fetch=fail)["error"] == "rfc_or_section_not_allowed"
    assert (
        get("9110", "3.1", fetch=lambda url, **_: (url, 200, {}, b"no headings"))["error"]
        == "section_not_found"
    )


def test_rfc_style_toc_duplicate_uses_meaningful_body_for_multiple_sections() -> None:
    def fetch(url: str, **_: object) -> tuple[str, int, dict[str, str], bytes]:
        return url, 200, {}, TOC_AND_BODY

    resources = get("9110", "3.1", fetch=fetch)
    semantics = get("9110", "4", fetch=fetch)
    assert "resource identification" in resources["text_slice"]
    assert "................................" not in resources["text_slice"]
    assert "HTTP semantics" in semantics["text_slice"]


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"get"}
    assert {item.name for item in build_skill()._pending} == {"get"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/rfc-section"
        ).direct_mcp_path
        == "/stars/rfc-section/mcp"
    )
