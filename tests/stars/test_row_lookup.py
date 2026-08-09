import hashlib
from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.row_lookup.contract import FLIGHTS_AIRPORT_URL, tool_schemas
from stars.row_lookup.service import lookup
from stars.row_lookup.skill import build_skill

SOURCE = b"origin,destination,count\nABE,ATL,853\nABE,BHM,1\n"
KEY = {"origin": "ABE", "destination": "ATL"}


def test_exact_key_returns_one_typed_row_and_source_evidence() -> None:
    result = lookup(
        "flights-airport",
        KEY,
        fetch=lambda url, **_: (url, 200, {}, SOURCE),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert result["row"] == {"origin": "ABE", "destination": "ATL", "count": 853}
    assert (
        result["source_url"] == FLIGHTS_AIRPORT_URL
        and result["canonical_url"] == FLIGHTS_AIRPORT_URL
    )
    assert result["source_digest"] == f"sha256:{hashlib.sha256(SOURCE).hexdigest()}"
    assert result["key_schema"]["origin"]["pattern"] == "^[A-Z]{3}$"


def test_unknown_dataset_or_invalid_key_never_fetches_and_not_found_is_loud() -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert lookup("unknown", KEY, fetch=fail)["error"] == "dataset_not_allowed"
    assert lookup("flights-airport", {"origin": "ABE"}, fetch=fail)["error"] == "invalid_key"
    assert (
        lookup(
            "flights-airport",
            {"origin": "ABE", "destination": "ZZZ"},
            fetch=lambda url, **_: (url, 200, {}, SOURCE),
        )["error"]
        == "row_not_found"
    )


def test_rejects_escape_and_malformed_source() -> None:
    assert (
        lookup(
            "flights-airport",
            KEY,
            fetch=lambda _url, **_: (
                "https://raw.githubusercontent.com/other/data.csv",
                200,
                {},
                SOURCE,
            ),
        )["error"]
        == "redirect_not_allowed"
    )
    bad = b"origin,destination,count\nABE,ATL,nope\n"
    assert (
        lookup("flights-airport", KEY, fetch=lambda url, **_: (url, 200, {}, bad))["error"]
        == "source_malformed"
    )


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"lookup"}
    assert {item.name for item in build_skill()._pending} == {"lookup"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/row-lookup"
        ).direct_mcp_path
        == "/stars/row-lookup/mcp"
    )
