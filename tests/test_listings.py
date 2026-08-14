"""Opt-in publisher listing ingest (ADR 0012 / #442)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog import CATALOG
from catalog.agent_card import required_public_card_names
from catalog.store import replace_catalog
from listings.fetch import assert_public_https_url, fetch_and_cap
from listings.records import listing_to_record
from listings.schema import ListingError, assert_proof_of_control, parse_listing
from listings.store import (
    ALLOWLIST_PATH,
    load_allowlist_fixtures,
    reset_listing_store,
    upsert_listing,
)

FIXTURE = Path(__file__).resolve().parent.parent / "listings" / "fixtures" / "example-invoice.json"


def _fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


@pytest.fixture
def _restore_catalog():
    before = CATALOG.all()
    yield
    reset_listing_store()
    replace_catalog(before)


@pytest.mark.issue(442)
def test_parse_listing_lands_in_new_namespace() -> None:
    doc = parse_listing(_fixture_bytes())
    assert doc.spec == "orrery-listing/0.1"
    assert doc.desired_name == "publisher/invoice-check"
    assert doc.live_name == "new/invoice-check"
    assert doc.slug == "invoice-check"
    record = listing_to_record(doc)
    assert record.name == "new/invoice-check"
    assert record.index_tier == "newcomer"
    assert record.oracle_ok is False
    assert record.endpoint.startswith("https://")
    assert record.content_digest.startswith("sha256:")
    assert record.claimed_name == "publisher/invoice-check"


@pytest.mark.issue(442)
def test_parse_rejects_reserved_orrery_prefix() -> None:
    data = json.loads(_fixture_bytes())
    data["name"] = "orrery/invoice-check"
    with pytest.raises(ListingError) as exc:
        parse_listing(json.dumps(data).encode())
    assert exc.value.code == "reserved_name"


@pytest.mark.issue(442)
def test_parse_proof_of_control_requires_shared_domain() -> None:
    assert_proof_of_control(
        "https://example.com/.well-known/orrery.json",
        "https://mcp.example.com/invoice/mcp",
    )
    with pytest.raises(ListingError) as exc:
        assert_proof_of_control(
            "https://evil.example.net/.well-known/orrery.json",
            "https://mcp.example.com/invoice/mcp",
        )
    assert exc.value.code == "proof_of_control"


@pytest.mark.issue(442)
def test_parse_http_url_rejected_without_fetch() -> None:
    with pytest.raises(ListingError) as exc:
        fetch_and_cap(
            "http://example.com/.well-known/orrery.json",
            fetch=lambda _u: _fixture_bytes(),
        )
    assert exc.value.code == "https_only"


@pytest.mark.issue(442)
def test_allowlist_rejects_private_address() -> None:
    with pytest.raises(ListingError) as exc:
        assert_public_https_url("https://127.0.0.1/.well-known/orrery.json")
    assert exc.value.code in {"private_address", "https_only"}


@pytest.mark.issue(442)
def test_allowlist_fixture_merges_into_catalog(_restore_catalog) -> None:
    reset_listing_store()
    loaded = load_allowlist_fixtures(path=ALLOWLIST_PATH)
    assert loaded
    assert loaded[0].name == "new/invoice-check"
    upsert_listing(loaded[0])
    record = CATALOG.get("new/invoice-check")
    assert record is not None
    assert record.index_tier == "newcomer"
    assert record.oracle_ok is False
    assert record.claimed_name == "publisher/invoice-check"


@pytest.mark.issue(442)
def test_listings_exempt_from_agent_card_ci() -> None:
    assert "new/invoice-check" not in required_public_card_names()
    assert "publisher/invoice-check" not in required_public_card_names()
