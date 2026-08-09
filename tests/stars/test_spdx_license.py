import hashlib
import json
from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.spdx_license.contract import MAX_TEXT_CHARS, tool_schemas
from stars.spdx_license.service import get
from stars.spdx_license.skill import build_skill

URL = "https://spdx.org/licenses/MIT.json"
HUMAN_URL = "https://spdx.org/licenses/MIT.html"
RECORD = {
    "licenseId": "MIT",
    "name": "MIT License",
    "isOsiApproved": True,
    "isDeprecatedLicenseId": False,
    "seeAlso": ["https://opensource.org/license/mit/"],
    "licenseText": "Permission is hereby granted, free of charge.",
}
SOURCE = json.dumps(RECORD).encode()


def test_named_license_uses_injected_canonical_source_and_bounded_metadata() -> None:
    result = get(
        "MIT",
        fetch=lambda url, **_: (url, 200, {}, SOURCE),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert result["source_url"] == URL and result["canonical_url"] == HUMAN_URL
    assert result["license_id"] == "MIT" and result["name"] == "MIT License"
    assert result["is_osi_approved"] is True and result["is_deprecated_license_id"] is False
    assert result["see_also"] == ["https://opensource.org/license/mit/"]
    assert result["text_slice"] == RECORD["licenseText"] and result["status"] == 200
    assert result["source_digest"] == f"sha256:{hashlib.sha256(SOURCE).hexdigest()}"
    assert result["text_digest"] == (
        f"sha256:{hashlib.sha256(RECORD['licenseText'].encode()).hexdigest()}"
    )
    assert result["slice_digest"] == result["text_digest"]
    assert result["source"] == {"publisher": "SPDX", "format": "application/json"}


def test_unknown_identifier_never_fetches_and_malformed_sources_are_loud() -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert get("GPL-3.0-only", fetch=fail)["error"] == "license_not_allowed"
    assert (
        get("MIT", fetch=lambda _url, **_: (_url, 200, {}, b"not json"))["error"]
        == "source_malformed"
    )
    wrong_id = json.dumps({**RECORD, "licenseId": "Apache-2.0"}).encode()
    assert (
        get("MIT", fetch=lambda url, **_: (url, 200, {}, wrong_id))["error"] == "source_malformed"
    )


def test_rejects_redirects_and_bounds_license_text() -> None:
    long_source = json.dumps({**RECORD, "licenseText": "x" * (MAX_TEXT_CHARS + 1)}).encode()
    result = get("MIT", fetch=lambda url, **_: (url, 200, {}, long_source))
    assert len(result["text_slice"]) == MAX_TEXT_CHARS and result["slice_truncated"] is True
    assert (
        get(
            "MIT", fetch=lambda _url, **_: ("https://spdx.org/licenses/else.json", 200, {}, SOURCE)
        )["error"]
        == "redirect_not_allowed"
    )


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"get"}
    assert {item.name for item in build_skill()._pending} == {"get"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/spdx-license"
        ).direct_mcp_path
        == "/stars/spdx-license/mcp"
    )
