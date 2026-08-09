from stars.builtins import builtin_registry
from stars.row_validate.contract import tool_schemas
from stars.row_validate.service import validate
from stars.row_validate.skill import build_skill

ROW = {"origin": "ABE", "destination": "ATL", "count": 853}


def test_valid_row_returns_normalized_value_and_deterministic_profile_digest() -> None:
    first = validate("flights-airport", ROW)
    second = validate("flights-airport", ROW)
    assert first["valid"] is True and first["normalized_row"] == ROW
    assert first["profile_digest"] == second["profile_digest"]


def test_invalid_type_pattern_count_missing_and_extra_fields_are_structured() -> None:
    result = validate(
        "flights-airport", {"origin": "ab", "destination": 3, "count": -1, "extra": 1}
    )
    assert result["valid"] is False
    assert {(item["path"], item["code"]) for item in result["errors"]} == {
        ("$.origin", "pattern"),
        ("$.destination", "type"),
        ("$.count", "minimum"),
        ("$.extra", "additional_property"),
    }
    assert (
        validate("flights-airport", {"origin": "ABE", "count": 1})["errors"][0]["code"]
        == "required"
    )


def test_unknown_profile_and_package_contract() -> None:
    assert validate("other", ROW)["error"] == "profile_not_allowed"
    assert set(tool_schemas()) == {"validate"}
    assert {item.name for item in build_skill()._pending} == {"validate"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/row-validate"
        ).direct_mcp_path
        == "/stars/row-validate/mcp"
    )
