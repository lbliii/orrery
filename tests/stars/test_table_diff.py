from stars.builtins import builtin_registry
from stars.table_diff.contract import MAX_ROWS, tool_schemas
from stars.table_diff.service import diff
from stars.table_diff.skill import build_skill


def test_equal_add_remove_and_changed_rows_include_provenance() -> None:
    left = {
        "rows": [
            {"id": "same", "price": 10, "active": True},
            {"id": "changed", "price": 10, "active": True},
            {"id": "removed", "price": 10, "active": False},
        ],
        "digest": "sha256:csv-left",
    }
    right = {
        "rows": [
            {"id": "same", "price": 10, "active": True},
            {"id": "changed", "price": 12, "active": False},
            {"id": "added", "price": 15, "active": True},
        ],
        "digest": "sha256:csv-right",
    }
    result = diff(left, right, "id")
    assert (result["added_count"], result["removed_count"], result["changed_count"]) == (1, 1, 1)
    assert result["unchanged_count"] == 1
    assert result["added"] == [{"id": "added"}] and result["removed"] == [{"id": "removed"}]
    assert result["changed"] == [
        {
            "id": "changed",
            "changed_columns": {
                "active": {"before": True, "after": False},
                "price": {"before": 10, "after": 12},
            },
        }
    ]
    assert result["left"]["caller_digest_claim"] == "sha256:csv-left"
    assert result["left"]["snapshot_digest"].startswith("sha256:")


def test_digest_and_order_are_deterministic() -> None:
    first = diff(
        {"rows": [{"id": "b", "value": 2}, {"id": "a", "value": 1}]},
        {"rows": [{"id": "a", "value": 1}, {"id": "b", "value": 3}]},
        "id",
    )
    second = diff(
        {"rows": [{"value": 1, "id": "a"}, {"value": 2, "id": "b"}]},
        {"rows": [{"value": 3, "id": "b"}, {"value": 1, "id": "a"}]},
        "id",
    )
    assert first["left"]["snapshot_digest"] == second["left"]["snapshot_digest"]
    assert first["right"]["snapshot_digest"] == second["right"]["snapshot_digest"]
    assert (
        first["changed"]
        == second["changed"]
        == [{"id": "b", "changed_columns": {"value": {"before": 2, "after": 3}}}]
    )


def test_validation_rejects_schema_keys_and_bounds() -> None:
    assert (
        diff({"rows": [{"id": "a"}]}, {"rows": [{"name": "a"}]}, "id")["error"]
        == "invalid_snapshot"
    )
    assert (
        diff({"rows": [{"id": "a"}, {"id": "a"}]}, {"rows": []}, "id")["error"]
        == "invalid_snapshot"
    )
    assert (
        diff({"rows": [{"id": "a", "nested": []}]}, {"rows": []}, "id")["error"]
        == "invalid_snapshot"
    )
    too_many = [{"id": str(number)} for number in range(MAX_ROWS + 1)]
    assert diff({"rows": too_many}, {"rows": []}, "id")["error"] == "invalid_snapshot"
    oversized = [{"id": str(number), "value": "x" * 700} for number in range(MAX_ROWS)]
    assert diff({"rows": oversized}, {"rows": []}, "id")["error"] == "invalid_snapshot"


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"diff"}
    assert {item.name for item in build_skill()._pending} == {"diff"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/table-diff"
        ).direct_mcp_path
        == "/stars/table-diff/mcp"
    )
