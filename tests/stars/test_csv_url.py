import hashlib
from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.csv_url.contract import DATASET_URLS, MAX_ROWS, tool_schemas
from stars.csv_url.service import get
from stars.csv_url.skill import build_skill

URL = "https://raw.githubusercontent.com/vega/vega-datasets/main/data/flights-airport.csv"
SOURCE = b"airport,flights,international\nJFK,25.0,true\nLAX,,false\n"


def test_named_dataset_uses_exact_canonical_source_and_typed_bounded_rows() -> None:
    result = get(
        "flights-airport",
        fetch=lambda url, **_: (url, 200, {}, SOURCE),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert result["source_url"] == URL and result["canonical_url"] == URL
    assert result["status"] == 200 and result["row_count"] == 2
    assert result["schema"] == {
        "airport": "string",
        "flights": "number",
        "international": "boolean",
    }
    assert result["rows"] == [
        {"airport": "JFK", "flights": 25.0, "international": True},
        {"airport": "LAX", "flights": None, "international": False},
    ]
    assert result["source_digest"] == f"sha256:{hashlib.sha256(SOURCE).hexdigest()}"
    assert result["source"] == {"publisher": "Vega Datasets", "format": "text/csv"}


def test_unknown_dataset_never_fetches_and_malformed_csv_is_loud() -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert get("anything", fetch=fail)["error"] == "dataset_not_allowed"
    malformed = b'name,year\n"unclosed,2020'
    assert (
        get("flights-airport", fetch=lambda url, **_: (url, 200, {}, malformed))["error"]
        == "source_malformed"
    )
    uneven = b"name,year\nPinto,1971,unexpected\n"
    assert (
        get("flights-airport", fetch=lambda url, **_: (url, 200, {}, uneven))["error"]
        == "source_malformed"
    )


def test_rejects_final_source_escape_and_truncates_rows() -> None:
    source = b"value\n" + b"\n".join(str(number).encode() for number in range(MAX_ROWS + 1))
    result = get("flights-airport", fetch=lambda url, **_: (url, 200, {}, source))
    assert result["row_count"] == MAX_ROWS + 1
    assert len(result["rows"]) == MAX_ROWS and result["rows_truncated"] is True
    assert (
        get(
            "flights-airport",
            fetch=lambda _url, **_: (
                "https://raw.githubusercontent.com/vega/other/main/data/flights-airport.csv",
                200,
                {},
                SOURCE,
            ),
        )["error"]
        == "redirect_not_allowed"
    )


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"get"}
    assert {item.name for item in build_skill()._pending} == {"get"}
    assert (
        next(item for item in builtin_registry() if item.name == "orrery/csv-url").direct_mcp_path
        == "/stars/csv-url/mcp"
    )


def test_catalog_contains_only_documented_vega_csv_paths() -> None:
    assert DATASET_URLS == {
        "airports": "https://raw.githubusercontent.com/vega/vega-datasets/main/data/airports.csv",
        "flights-airport": URL,
        "seattle-weather": (
            "https://raw.githubusercontent.com/vega/vega-datasets/main/data/seattle-weather.csv"
        ),
    }
