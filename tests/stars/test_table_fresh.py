from catalog.constellation import policy_for
from stars.builtins import builtin_registry
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


def test_malformed_baseline_is_not_coerced_to_an_empty_table() -> None:
    assert run({"rows": [{"origin": "ABE", "count": 853}]}, csv_fetch=_fetch) == {
        "error": "invalid_baseline",
        "scope": "bounded_sample",
    }


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
