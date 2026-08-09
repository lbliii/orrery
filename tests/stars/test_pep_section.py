from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.pep_section.contract import tool_schemas
from stars.pep_section.service import get
from stars.pep_section.skill import build_skill

URL = "https://peps.python.org/pep-0008/"
HTML = (
    b"<html><body><nav><h2>Introduction</h2><p>TOC only</p></nav>"
    b"<h2>Introduction</h2><p>Body guidance is meaningful.</p>"
    b"<h2>Code Layout</h2><p>Use four spaces.</p></body></html>"
)


def test_canonical_pep_html_returns_body_not_toc_and_digests() -> None:
    result = get(
        "8",
        "Introduction",
        fetch=lambda url, **_: (url, 200, {}, HTML),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert result["canonical_url"] == URL and result["text_slice"] == "Body guidance is meaningful."
    assert result["source_digest"].startswith("sha256:") and result["slice_digest"].startswith(
        "sha256:"
    )


def test_named_only_policy_never_fetches_and_code_layout_works() -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert get("20", "The Zen", fetch=fail)["error"] == "pep_or_section_not_allowed"
    assert get("8", "nope", fetch=fail)["error"] == "pep_or_section_not_allowed"
    result = get("8", "Code Layout", fetch=lambda url, **_: (url, 200, {}, HTML))
    assert "four spaces" in result["text_slice"]


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"get"}
    assert {item.name for item in build_skill()._pending} == {"get"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/pep-section"
        ).direct_mcp_path
        == "/stars/pep-section/mcp"
    )
