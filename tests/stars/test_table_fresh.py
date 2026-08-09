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
    changed = run(
        {"rows": [{"origin": "ABE", "destination": "ATL", "count": 800}]}, csv_fetch=_fetch
    )
    assert changed["diff"]["changed_count"] == 1 and changed["current_source"][
        "source_digest"
    ].startswith("sha256:")
    assert changed["baseline"]["snapshot_digest"].startswith("sha256:")


def test_constellation_definition_and_direct_skill() -> None:
    definition = builtin_registry().get("orrery/table-fresh")
    assert (
        definition.kind == "constellation"
        and definition.direct_mcp_path == "/constellations/table-fresh/mcp"
    )
    assert {item.name for item in build_skill()._pending} == {"run"}
