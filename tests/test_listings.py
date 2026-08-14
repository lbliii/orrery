"""Opt-in publisher listing ingest (ADR 0012 / #442)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from chirp.testing import TestClient

from catalog import CATALOG
from catalog.agent_card import required_public_card_names
from catalog.store import replace_catalog
from listings.fetch import assert_public_https_url, fetch_and_cap
from listings.ping import ping_listing
from listings.promote import apply_promotion, promotion_ready
from listings.records import listing_to_record
from listings.schema import ListingError, assert_proof_of_control, parse_listing
from listings.store import (
    ALLOWLIST_PATH,
    load_allowlist_fixtures,
    reset_listing_store,
    upsert_listing,
)
from namespaces.validation import is_reserved_slug
from trust.satisfaction import InMemorySatisfactionStore, SatisfactionRecord

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


def _seed_newcomer(_restore_catalog) -> None:
    reset_listing_store()
    loaded = load_allowlist_fixtures(path=ALLOWLIST_PATH)
    assert loaded
    upsert_listing(loaded[0])


@pytest.mark.issue(443)
def test_gaze_node_new_and_newcomer_facet(_restore_catalog) -> None:
    _seed_newcomer(_restore_catalog)
    record = CATALOG.get("new/invoice-check")
    assert record is not None
    nodes = {n.id for n in CATALOG.gaze_nodes()}
    assert "new" in nodes
    hits = CATALOG.match("invoice", node="new")
    assert any(h.name == "new/invoice-check" for h in hits)
    hit = next(h for h in hits if h.name == "new/invoice-check")
    wire = hit.as_dict()
    assert wire["index_tier"] == "newcomer"
    assert wire["oracle_ok"] is False
    assert "rate_listing" in (wire["rate_after_verify"] or "")
    described = CATALOG.describe("new/invoice-check")
    assert described["index_tier"] == "newcomer"
    assert "rate_listing" in described["rate_after_verify"]


@pytest.mark.issue(443)
def test_empty_intent_browse_keeps_first_party_ahead(example_app, _restore_catalog) -> None:
    _seed_newcomer(_restore_catalog)
    hits = CATALOG.hits_for_node("public")
    names = [h.name for h in hits]
    assert "orrery/html-to-pdf" in names
    if "new/invoice-check" in names:
        assert names.index("orrery/html-to-pdf") < names.index("new/invoice-check")


@pytest.mark.issue(443)
@pytest.mark.asyncio
async def test_stars_page_excludes_newcomers(example_app, _restore_catalog) -> None:
    _seed_newcomer(_restore_catalog)
    async with TestClient(example_app) as client:
        response = await client.get("/stars")
    assert response.status == 200
    assert "new/invoice-check" not in response.text
    assert "orrery/html-to-pdf" in response.text


@pytest.mark.issue(444)
def test_reserved_namespace_new() -> None:
    assert is_reserved_slug("new")


@pytest.mark.issue(444)
@pytest.mark.asyncio
async def test_reserved_new_namespace_returns_400(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.post("/api/namespaces", json={"id": "new"})
    assert response.status == 400
    assert json.loads(response.text)["error"] == "reserved_slug"


@pytest.mark.issue(444)
def test_ping_listing_lands_immediately(_restore_catalog) -> None:
    record = ping_listing(
        "https://example.com/.well-known/orrery.json",
        fetch=lambda _u: _fixture_bytes(),
    )
    assert record.name == "new/invoice-check"
    assert CATALOG.get("new/invoice-check") is not None


@pytest.mark.issue(444)
@pytest.mark.asyncio
async def test_http_ping_rejects_http(example_app) -> None:
    async with TestClient(example_app) as client:
        response = await client.post(
            "/api/listings/ping",
            json={"url": "http://example.com/.well-known/orrery.json"},
        )
    assert response.status == 400
    assert json.loads(response.text)["error"] == "https_only"


@pytest.mark.issue(444)
def test_boot_fixture_present_after_app_import(example_app) -> None:
    record = CATALOG.get("new/invoice-check")
    assert record is not None
    assert record.index_tier == "newcomer"
    assert record.oracle_ok is False


@pytest.mark.issue(446)
def test_promotion_ready_requires_distinct_callers() -> None:
    ratings = [
        SatisfactionRecord(
            star_name="new/invoice-check",
            content_digest="sha256:abc",
            verdict="useful",
            created_at="2026-08-14T12:00:00Z",
            envelope_id=f"env-{i}",
            caller_namespace="same-swarm",
        )
        for i in range(20)
    ]
    assert (
        promotion_ready(
            ratings,
            star_name="new/invoice-check",
            content_digest="sha256:abc",
            min_useful=10,
            min_callers=10,
        )
        is False
    )


@pytest.mark.issue(446)
def test_apply_promotion_moves_claimed_name(example_app, _restore_catalog, monkeypatch) -> None:
    store = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", store)
    live = CATALOG.get("new/invoice-check")
    assert live is not None
    digest = live.content_digest
    for i in range(10):
        store.put(
            SatisfactionRecord(
                star_name="new/invoice-check",
                content_digest=digest,
                verdict="useful",
                created_at="2026-08-14T12:00:00Z",
                envelope_id=f"env-{i}",
                caller_namespace=f"caller-{i}",
            )
        )
    promoted = apply_promotion(
        "new/invoice-check",
        min_useful=10,
        min_callers=10,
    )
    assert promoted is not None
    assert promoted.name == "publisher/invoice-check"
    assert promoted.index_tier == "registered"
    alias = CATALOG.get("new/invoice-check")
    assert alias is not None
    assert alias.promoted_to == "publisher/invoice-check"
    claimed = CATALOG.get("publisher/invoice-check")
    assert claimed is not None
    assert claimed.oracle_ok is False
