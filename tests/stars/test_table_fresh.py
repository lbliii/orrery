from pathlib import Path

from catalog.agent_card import require_card
from catalog.constellation import policy_for
from stars.builtins import builtin_registry
from stars.table_fresh.contract import EXAMPLE_BASELINE, tool_schemas
from stars.table_fresh.service import run
from stars.table_fresh.skill import build_skill

SOURCE = b"origin,destination,count\nABE,ATL,853\nABE,BHM,1\n"


def _fetch(url: str, **_: object) -> tuple[str, int, dict[str, str], bytes]:
    return url, 200, {}, SOURCE


def test_real_csv_to_diff_composition_is_unchanged_or_changed() -> None:
    baseline = {
        "rows": [
            {"origin": "ABE", "destination": "ATL", "count": 853},
            {"origin": "ABE", "destination": "BHM", "count": 1},
        ],
        "source_digest": "sha256:prior",
    }
    unchanged = run(baseline, csv_fetch=_fetch)
    assert unchanged["scope"] == "bounded_sample" and unchanged["diff"]["changed_count"] == 0
    assert unchanged["verdict"] == "unchanged" and unchanged["current_rows_returned"] == 2
    changed = run(
        {"rows": [{"origin": "ABE", "destination": "ATL", "count": 800}]}, csv_fetch=_fetch
    )
    assert changed["diff"]["changed_count"] == 1 and changed["current_source"][
        "source_digest"
    ].startswith("sha256:")
    assert changed["baseline"]["snapshot_digest"].startswith("sha256:")
    assert changed["verdict"] == "changed"


def test_malformed_baseline_returns_remediation_not_bare_code() -> None:
    result = run({"rows": [{"origin": "ABE", "count": 853}]}, csv_fetch=_fetch)
    assert result["error"] == "invalid_baseline"
    assert result["scope"] == "bounded_sample"
    remediation = result.get("remediation")
    assert isinstance(remediation, str) and remediation.strip()
    assert "origin" in remediation and "destination" in remediation and "count" in remediation
    example = result.get("example")
    assert isinstance(example, dict) and example.get("rows")
    assert example["rows"][0] == {"origin": "ABE", "destination": "ATL", "count": 853}
    expected_shape = result.get("expected_shape")
    assert isinstance(expected_shape, dict) and "properties" in expected_shape


def test_dataset_baseline_is_invalid_with_remediation() -> None:
    result = run({"dataset": "flights-sample"}, csv_fetch=_fetch)
    assert result["error"] == "invalid_baseline"
    remediation = str(result.get("remediation", ""))
    assert remediation.strip()
    assert "rows" in remediation.lower() or "dataset" in remediation.lower()


def test_published_baseline_example_matches_fixture() -> None:
    doc = Path("docs/operations/table-fresh.md").read_text()
    assert "ABE" in doc and "ATL" in doc and "853" in doc
    card = require_card("orrery/table-fresh")
    example = card.run_contract["input_bundle"]["baseline"]["example"]
    assert example == EXAMPLE_BASELINE


def test_run_tool_schema_matches_contract() -> None:
    assert set(tool_schemas()) == {"run"}
    schema = tool_schemas()["run"]["inputSchema"]
    assert schema["required"] == ["baseline"]
    assert schema["properties"]["baseline"]["required"] == ["rows"]


def test_constellation_definition_and_direct_skill() -> None:
    definition = builtin_registry().get("orrery/table-fresh")
    assert (
        definition.kind == "constellation"
        and definition.direct_mcp_path == "/constellations/table-fresh/mcp"
    )
    assert {item.name for item in build_skill()._pending} == {"run"}
    graph = policy_for("orrery/table-fresh")
    assert graph is not None
    assert [node.star_ref for node in graph.nodes if node.star_ref] == [
        "orrery/csv-url",
        "orrery/table-diff",
    ]
