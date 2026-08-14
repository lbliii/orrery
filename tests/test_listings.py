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
from listings.job import refetch_known
from listings.ping import ping_listing
from listings.postgres import PostgresListingStore
from listings.promote import apply_promotion, promotion_ready, should_quiet
from listings.records import listing_to_record
from listings.schema import ListingError, assert_proof_of_control, parse_listing
from listings.store import (
    ALLOWLIST_PATH,
    InMemoryListingStore,
    ListingRow,
    ListingStoreConfigError,
    boot_durable_listings,
    configure_listing_store,
    list_urls,
    listing_records,
    listing_store_from_env,
    load_allowlist_fixtures,
    quiet_names,
    reset_listing_store,
    set_quiet,
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
    configure_listing_store(None)
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
        store=InMemoryListingStore(),
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


def _listing_bytes(*, name: str) -> bytes:
    data = json.loads(_fixture_bytes())
    data["name"] = name
    return json.dumps(data).encode()


@pytest.mark.issue(458)
def test_ping_survives_simulated_restart(_restore_catalog) -> None:
    ping_url = "https://example.com/.well-known/orrery.json"
    backing: dict[str, ListingRow] = {}
    first = InMemoryListingStore(backing)
    ping_listing(
        ping_url,
        fetch=lambda _u: _listing_bytes(name="publisher/restart-probe"),
        store=first,
    )
    assert CATALOG.get("new/restart-probe") is not None

    kept = tuple(r for r in CATALOG.all() if r.name != "new/restart-probe")
    replace_catalog(kept)
    reset_listing_store()
    assert CATALOG.get("new/restart-probe") is None

    reloaded = InMemoryListingStore(backing)
    boot_durable_listings(store=reloaded)
    fixtures = load_allowlist_fixtures(path=ALLOWLIST_PATH)
    assert fixtures
    assert any(row.name == "new/invoice-check" for row in listing_records())
    revived = CATALOG.get("new/restart-probe")
    assert revived is not None
    assert revived.listing_url == ping_url
    assert list_urls(store=reloaded) == (ping_url,)


@pytest.mark.issue(458)
def test_list_urls_returns_only_known_listing_urls(_restore_catalog) -> None:
    store = InMemoryListingStore()
    load_allowlist_fixtures(path=ALLOWLIST_PATH)
    assert list_urls(store=store) == ()
    ping_url = "https://example.com/.well-known/orrery.json"
    ping_listing(ping_url, fetch=lambda _u: _fixture_bytes(), store=store)
    assert list_urls(store=store) == (ping_url,)
    assert all(not url.startswith("fixture://") for url in list_urls(store=store))


@pytest.mark.issue(458)
def test_postgres_store_requires_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ListingStoreConfigError, match="DATABASE_URL"):
        PostgresListingStore()


@pytest.mark.issue(458)
def test_host_factory_selects_postgres_when_database_url_set(
    monkeypatch, _restore_catalog
) -> None:
    configure_listing_store(None)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/orrery")
    store = listing_store_from_env()
    assert isinstance(store, PostgresListingStore)


@pytest.mark.issue(458)
def test_deployed_ping_without_database_url_is_store_unavailable(
    monkeypatch, _restore_catalog
) -> None:
    configure_listing_store(None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ListingError) as exc:
        ping_listing(
            "https://example.com/.well-known/orrery.json",
            fetch=lambda _u: _fixture_bytes(),
        )
    assert exc.value.code == "store_unavailable"


PING_URL = "https://example.com/.well-known/orrery.json"


def _put_sealed(
    store: InMemorySatisfactionStore,
    *,
    star_name: str,
    digest: str,
    verdict: str,
    envelope_id: str,
    caller_namespace: str = "caller-1",
) -> None:
    store.put(
        SatisfactionRecord(
            star_name=star_name,
            content_digest=digest,
            verdict=verdict,
            created_at="2026-08-14T12:00:00Z",
            envelope_id=envelope_id,
            caller_namespace=caller_namespace,
        )
    )


@pytest.mark.issue(460)
def test_refetch_known_fetches_only_stored_urls(_restore_catalog) -> None:
    store = InMemoryListingStore()
    ping_listing(
        PING_URL,
        fetch=lambda _u: _listing_bytes(name="publisher/refetch-only"),
        store=store,
    )
    called: list[str] = []

    def spy(url: str) -> bytes:
        called.append(url)
        return _listing_bytes(name="publisher/refetch-only")

    result = refetch_known(fetch=spy, store=store)
    assert called == [PING_URL]
    assert result.urls == (PING_URL,)
    assert result.fetched == (PING_URL,)


@pytest.mark.issue(460)
def test_refetch_known_does_not_fetch_when_store_empty(_restore_catalog) -> None:
    called: list[str] = []
    refetch_known(
        fetch=lambda url: called.append(url) or _fixture_bytes(),
        store=InMemoryListingStore(),
    )
    assert called == []


@pytest.mark.issue(460)
def test_should_quiet_thresholds_remain_injectable() -> None:
    ratings = [
        SatisfactionRecord(
            star_name="new/invoice-check",
            content_digest="sha256:abc",
            verdict="broken",
            created_at="2026-08-14T12:00:00Z",
            envelope_id="env-b",
        ),
        *[
            SatisfactionRecord(
                star_name="new/invoice-check",
                content_digest="sha256:abc",
                verdict="useful",
                created_at="2026-08-14T12:00:00Z",
                envelope_id=f"env-u{i}",
            )
            for i in range(3)
        ],
    ]
    assert (
        should_quiet(
            ratings,
            star_name="new/invoice-check",
            content_digest="sha256:abc",
            max_broken_ratio=0.25,
        )
        is False
    )
    assert (
        should_quiet(
            ratings,
            star_name="new/invoice-check",
            content_digest="sha256:abc",
            max_broken_ratio=0.2,
        )
        is True
    )


@pytest.mark.issue(460)
def test_should_quiet_ignores_unsealed_and_other_digest() -> None:
    ratings = [
        SatisfactionRecord(
            star_name="new/invoice-check",
            content_digest="sha256:abc",
            verdict="broken",
            created_at="2026-08-14T12:00:00Z",
            call_attempt_id="attempt-1",
        ),
        SatisfactionRecord(
            star_name="new/invoice-check",
            content_digest="sha256:other",
            verdict="broken",
            created_at="2026-08-14T12:00:00Z",
            envelope_id="env-other",
        ),
    ]
    assert (
        should_quiet(
            ratings,
            star_name="new/invoice-check",
            content_digest="sha256:abc",
        )
        is False
    )


@pytest.mark.issue(460)
def test_refetch_known_promotes_with_injected_thresholds(
    example_app, _restore_catalog, monkeypatch
) -> None:
    listing_store = InMemoryListingStore()
    sat = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", sat)
    record = ping_listing(
        PING_URL,
        fetch=lambda _u: _listing_bytes(name="publisher/refetch-promote"),
        store=listing_store,
    )
    for i in range(10):
        _put_sealed(
            sat,
            star_name=record.name,
            digest=record.content_digest,
            verdict="useful",
            envelope_id=f"env-{i}",
            caller_namespace=f"caller-{i}",
        )
    result = refetch_known(
        fetch=lambda _u: _listing_bytes(name="publisher/refetch-promote"),
        store=listing_store,
        min_useful=10,
        min_callers=10,
    )
    assert "publisher/refetch-promote" in result.promoted
    claimed = CATALOG.get("publisher/refetch-promote")
    assert claimed is not None
    assert claimed.index_tier == "registered"


@pytest.mark.issue(460)
def test_refetch_known_quiets_live_digest_and_stays_resolvable(
    example_app, _restore_catalog, monkeypatch
) -> None:
    listing_store = InMemoryListingStore()
    configure_listing_store(listing_store)
    sat = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", sat)
    record = ping_listing(
        PING_URL,
        fetch=lambda _u: _listing_bytes(name="publisher/refetch-quiet"),
        store=listing_store,
    )
    _put_sealed(
        sat,
        star_name=record.name,
        digest=record.content_digest,
        verdict="broken",
        envelope_id="env-broken",
    )
    result = refetch_known(
        fetch=lambda _u: _listing_bytes(name="publisher/refetch-quiet"),
        store=listing_store,
    )
    row = listing_store.get(PING_URL)
    assert row is not None
    assert row.quiet is True
    assert record.name in result.quieted
    assert record.name in quiet_names(store=listing_store)
    public_names = [h.name for h in CATALOG.hits_for_node("public")]
    assert record.name not in public_names
    assert CATALOG.get(record.name) is not None
    assert CATALOG.resolve(record.name) is not None


@pytest.mark.issue(460)
def test_refetch_known_quiets_after_failed_fetch(
    _restore_catalog, monkeypatch
) -> None:
    listing_store = InMemoryListingStore()
    sat = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", sat)
    record = ping_listing(
        PING_URL,
        fetch=lambda _u: _listing_bytes(name="publisher/refetch-fail"),
        store=listing_store,
    )
    _put_sealed(
        sat,
        star_name=record.name,
        digest=record.content_digest,
        verdict="wrong-price",
        envelope_id="env-wp",
    )
    result = refetch_known(fetch=lambda _u: b"{", store=listing_store)
    assert result.fetched == ()
    assert result.errors
    row = listing_store.get(PING_URL)
    assert row is not None
    assert row.quiet is True
    assert row.last_error is not None
    assert CATALOG.get(record.name) is not None


@pytest.mark.issue(460)
def test_set_quiet_does_not_invent_hosts(_restore_catalog) -> None:
    store = InMemoryListingStore()
    assert set_quiet("https://unknown.example/.well-known/orrery.json", store=store) is None
    assert quiet_names(store=store) == frozenset()
