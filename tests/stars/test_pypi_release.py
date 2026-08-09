import json
from datetime import UTC, datetime

from stars.pypi_release.contract import tool_schemas
from stars.pypi_release.service import get
from stars.pypi_release.skill import build_skill

SOURCE = json.dumps(
    {
        "info": {
            "version": "1.2.3",
            "summary": "test",
            "requires_python": ">=3.10",
            "project_urls": {"Docs": "https://example.test"},
        },
        "releases": {
            "1.2.3": [
                {
                    "filename": "x.whl",
                    "upload_time_iso_8601": "2026-01-01T00:00:00Z",
                    "digests": {"sha256": "abc"},
                    "yanked": False,
                }
            ]
        },
    }
).encode()
URL = "https://pypi.org/pypi/httpx/json"


def test_canonical_fixture_and_unknown_no_fetch() -> None:
    result = get(
        "httpx",
        fetch=lambda url, **_: (url, 200, {"ETag": "tag"}, SOURCE),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert (
        result["version"] == "1.2.3"
        and result["artifacts"][0]["sha256"] == "abc"
        and result["etag"] == "tag"
    )

    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert get("other", fetch=fail)["error"] == "package_not_allowed"


def test_rejects_malformed_and_escape_and_contract() -> None:
    assert (
        get("httpx", fetch=lambda _url, **_: ("https://pypi.org/pypi/other/json", 200, {}, SOURCE))[
            "error"
        ]
        == "redirect_not_allowed"
    )
    assert (
        get("httpx", fetch=lambda url, **_: (url, 200, {}, b"bad"))["error"] == "source_malformed"
    )
    assert set(tool_schemas()) == {"get"} and {item.name for item in build_skill()._pending} == {
        "get"
    }
