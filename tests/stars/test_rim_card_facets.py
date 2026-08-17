"""Rim agent cards advertise tree_role / worker_cost facets (#312)."""

from __future__ import annotations

import pytest

from catalog.agent_card import require_card

# decision-bind → planner; protocol sensors → worker/low; review-ish → review/low
_RIM_STAR_FACETS: dict[str, tuple[str, str | None]] = {
    "orrery/decision-bind": ("planner", None),
    "orrery/acceptance-bind": ("planner", None),
    "orrery/manifest-bind": ("worker", "low"),
    "orrery/manifest-preflight": ("review", "low"),
    "orrery/patch-capture": ("worker", "low"),
    "orrery/structure-audit": ("review", "low"),
    "orrery/plugin-preflight": ("worker", "low"),
    "orrery/link-check-bounded": ("review", "low"),
    "orrery/write-authority-check": ("review", "low"),
}

# Key rim constellations already publishing cards (composite cost = mid).
_RIM_CONSTELLATION_FACETS: dict[str, tuple[str, str]] = {
    "orrery/content-readiness": ("review", "mid"),
    "orrery/plugin-readiness": ("review", "mid"),
    "orrery/authorized-content-patch": ("worker", "mid"),
    "orrery/publish-gate": ("review", "mid"),
    "orrery/ship-check": ("review", "mid"),
    "orrery/stale-proof": ("review", "mid"),
}


@pytest.mark.issue(312)
@pytest.mark.parametrize("name,expected", sorted(_RIM_STAR_FACETS.items()))
def test_rim_star_tree_role_and_worker_cost(
    name: str, expected: tuple[str, str | None]
) -> None:
    role, cost = expected
    card = require_card(name)
    assert card.tree_role == role
    assert card.worker_cost == cost
    payload = card.as_dict()
    assert payload["tree_role"] == role
    preview = card.gaze_preview()
    assert preview["tree_role"] == role
    if cost is None:
        assert "worker_cost" not in payload
        assert "worker_cost" not in preview
    else:
        assert payload["worker_cost"] == cost
        assert preview["worker_cost"] == cost


@pytest.mark.issue(312)
@pytest.mark.parametrize("name,expected", sorted(_RIM_CONSTELLATION_FACETS.items()))
def test_rim_constellation_tree_role_and_worker_cost(
    name: str, expected: tuple[str, str]
) -> None:
    role, cost = expected
    card = require_card(name)
    assert card.tree_role == role
    assert card.worker_cost == cost
    payload = card.as_dict()
    preview = card.gaze_preview()
    assert payload["tree_role"] == role
    assert payload["worker_cost"] == cost
    assert preview["tree_role"] == role
    assert preview["worker_cost"] == cost


@pytest.mark.issue(312)
def test_non_rim_cards_keep_tree_role_and_worker_cost_absent() -> None:
    card = require_card("orrery/world-time")
    assert card.tree_role is None
    assert card.worker_cost is None
    assert "tree_role" not in card.as_dict()
    assert "worker_cost" not in card.gaze_preview()
