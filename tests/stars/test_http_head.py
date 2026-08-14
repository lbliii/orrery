from __future__ import annotations

from datetime import UTC, datetime

from stars._core import http_egress
from stars._core.http_egress import NoRedirect
from stars.builtins import builtin_registry
from stars.http_head.contract import tool_schemas
from stars.http_head.service import head
from stars.http_head.skill import build_skill


def test_head_returns_bounded_fresh_metadata_from_injected_transport() -> None:
    result = head(
        "python-3.14-whatsnew",
        transport=lambda url, **_: (
            url,
            200,
            {"ETag": '"abc"', "Content-Length": "42", "Content-Type": "text/html"},
        ),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert result == {
        "target": "python-3.14-whatsnew",
        "requested_url": "https://docs.python.org/3/whatsnew/3.14.html",
        "final_url": "https://docs.python.org/3/whatsnew/3.14.html",
        "status": 200,
        "etag": '"abc"',
        "last_modified": None,
        "content_type": "text/html",
        "content_length": "42",
        "observed_at": "2026-08-09T00:00:00+00:00",
        "live_at_call": True,
    }


def test_head_rejects_unknown_target_and_redirect_escape_without_transporting_unknown() -> None:
    assert head("https://evil.example/")["error"] == "target_not_allowed"
    result = head("timeapi-utc", transport=lambda _url, **_: ("https://evil.example/", 302, {}))
    assert result["error"] == "redirect_not_allowed"


def test_shared_https_egress_helper_is_transport_only() -> None:
    assert NoRedirect().redirect_request() is None
    assert not hasattr(http_egress, "ALLOWED_HOSTS")
    assert not hasattr(http_egress, "TARGETS")


def test_contract_skill_and_manifest_shape_are_discoverable() -> None:
    assert set(tool_schemas()) == {"head"}
    skill = build_skill()
    assert {tool.name for tool in skill._pending} == {"head"}
    definition = next(item for item in builtin_registry() if item.name == "orrery/http-head")
    assert definition.direct_mcp_path == "/stars/http-head/mcp"
