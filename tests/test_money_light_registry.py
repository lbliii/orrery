"""Registry completeness for money-light stars (#384)."""

from __future__ import annotations

import pytest

from catalog.agent_card import card_for, require_card
from catalog.sync import refresh_catalog
from stars.builtins import BUILTIN_STAR_PACKAGES, build_direct_skills, builtin_registry

FX_RATE = "orrery/fx-rate"
TAX_REGION = "orrery/tax-region"


@pytest.mark.issue(384)
def test_money_light_registry_builtin_packages() -> None:
    assert "stars.fx_rate" in BUILTIN_STAR_PACKAGES
    assert "stars.tax_region" in BUILTIN_STAR_PACKAGES


@pytest.mark.issue(384)
def test_money_light_registry_agent_cards() -> None:
    for name in (FX_RATE, TAX_REGION):
        assert card_for(name) is not None
        require_card(name)


@pytest.mark.issue(384)
def test_money_light_registry_catalog_refresh() -> None:
    registry = builtin_registry()
    records = refresh_catalog(registry, build_direct_skills(registry))
    names = {record.name for record in records}
    assert FX_RATE in names
    assert TAX_REGION in names
    fx = next(record for record in records if record.name == FX_RATE)
    tax = next(record for record in records if record.name == TAX_REGION)
    assert fx.agent_card is not None
    assert tax.agent_card is not None
    assert fx.endpoint.endswith("/stars/fx-rate/mcp")
    assert tax.endpoint.endswith("/stars/tax-region/mcp")
