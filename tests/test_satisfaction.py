"""MCP rate tool and satisfaction store (#68)."""

from __future__ import annotations

import logging

import pytest

from dogfood import signed_world_time_receipt, verify_receipt
from trust.satisfaction import (
    InMemorySatisfactionStore,
    SatisfactionRecord,
    SatisfactionStoreUnavailable,
    get_satisfaction_store,
    submit_rate,
)
from trust.satisfaction_postgres import PostgresSatisfactionStore

STAR_NAME = "orrery/world-time"
CONTENT_DIGEST = "sha256:abc123"


@pytest.fixture
def store() -> InMemorySatisfactionStore:
    return InMemorySatisfactionStore()


@pytest.fixture(autouse=True)
def _isolate_default_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests from leaking ratings into the process-wide stub."""
    fresh = InMemorySatisfactionStore()
    monkeypatch.setattr("trust.satisfaction._default_store", fresh)


@pytest.mark.issue(68)
def test_happy_path_put_with_verified_receipt(store: InMemorySatisfactionStore) -> None:
    receipt, verified = signed_world_time_receipt()
    assert verified is True

    result = submit_rate(
        star_name=STAR_NAME,
        content_digest=CONTENT_DIGEST,
        verdict="useful",
        envelope_id=str(receipt["nonce"]),
        receipt=receipt,
        store=store,
        verify_receipt=verify_receipt,
    )

    assert result["status"] == "ok"
    stored = result["record"]
    assert isinstance(stored, dict)
    assert stored["star_name"] == STAR_NAME
    assert stored["verdict"] == "useful"
    assert stored["envelope_id"] == receipt["nonce"]

    fetched = store.get_for_receipt(
        content_digest=CONTENT_DIGEST,
        envelope_id=str(receipt["nonce"]),
        call_attempt_id=None,
    )
    assert fetched is not None
    assert fetched.verdict == "useful"


@pytest.mark.issue(68)
def test_reject_without_receipt_authority(store: InMemorySatisfactionStore) -> None:
    missing = submit_rate(
        star_name=STAR_NAME,
        content_digest=CONTENT_DIGEST,
        verdict="useful",
        store=store,
        verify_receipt=verify_receipt,
    )
    assert missing["status"] == "rejected"
    assert missing["error"] == "missing_receipt_authority"

    receipt, _ = signed_world_time_receipt()
    no_receipt = submit_rate(
        star_name=STAR_NAME,
        content_digest=CONTENT_DIGEST,
        verdict="useful",
        envelope_id=str(receipt["nonce"]),
        store=store,
        verify_receipt=verify_receipt,
    )
    assert no_receipt["status"] == "rejected"
    assert no_receipt["error"] == "missing_receipt"


@pytest.mark.issue(68)
def test_digest_keyed_get(store: InMemorySatisfactionStore) -> None:
    digest_a = "sha256:aaa"
    digest_b = "sha256:bbb"

    submit_rate(
        star_name=STAR_NAME,
        content_digest=digest_a,
        verdict="stale",
        call_attempt_id="attempt-1",
        store=store,
        verify_receipt=verify_receipt,
    )
    submit_rate(
        star_name=STAR_NAME,
        content_digest=digest_b,
        verdict="broken",
        call_attempt_id="attempt-2",
        store=store,
        verify_receipt=verify_receipt,
    )

    assert store.get_for_receipt(
        content_digest=digest_a,
        envelope_id=None,
        call_attempt_id="attempt-1",
    ) is not None
    assert store.get_for_receipt(
        content_digest=digest_b,
        envelope_id=None,
        call_attempt_id="attempt-2",
    ) is not None
    assert store.get_for_receipt(
        content_digest=digest_a,
        envelope_id=None,
        call_attempt_id="attempt-2",
    ) is None

    agg = store.aggregate(star_name=STAR_NAME, content_digest=digest_a)
    assert agg.total == 1
    assert agg.counts == {"stale": 1}


@pytest.mark.issue(68)
def test_no_wallet_side_effects(store: InMemorySatisfactionStore, caplog) -> None:
    receipt, verified = signed_world_time_receipt()
    assert verified is True

    with caplog.at_level(logging.WARNING):
        result = submit_rate(
            star_name=STAR_NAME,
            content_digest=CONTENT_DIGEST,
            verdict="useful",
            envelope_id=str(receipt["nonce"]),
            receipt=receipt,
            store=store,
            verify_receipt=verify_receipt,
        )

    assert result["status"] == "ok"
    assert "commerce.charge_stub" not in caplog.text
    assert "commerce.refund_stub" not in caplog.text


@pytest.mark.issue(68)
def test_failed_call_token_path(store: InMemorySatisfactionStore) -> None:
    result = submit_rate(
        star_name=STAR_NAME,
        content_digest="sha256:deadbeef",
        verdict="broken",
        call_attempt_id="fail-attempt-99",
        store=store,
        verify_receipt=verify_receipt,
    )
    assert result["status"] == "ok"
    assert result["record"]["call_attempt_id"] == "fail-attempt-99"
    assert "envelope_id" not in result["record"]


@pytest.mark.issue(68)
def test_reject_invalid_receipt(store: InMemorySatisfactionStore) -> None:
    receipt, _ = signed_world_time_receipt()
    forged = dict(receipt)
    forged["nonce"] = "tampered"

    result = submit_rate(
        star_name=STAR_NAME,
        content_digest="sha256:deadbeef",
        verdict="useful",
        envelope_id=str(receipt["nonce"]),
        receipt=forged,
        store=store,
        verify_receipt=verify_receipt,
    )
    assert result["status"] == "rejected"
    assert result["error"] == "invalid_receipt"


@pytest.mark.issue(68)
def test_default_store_singleton() -> None:
    store = get_satisfaction_store()
    assert isinstance(store, InMemorySatisfactionStore)


@pytest.mark.issue(459)
def test_postgres_put_survives_new_store_instance() -> None:
    backend = _RowStore()
    first = PostgresSatisfactionStore(lambda: _Connection(backend))
    first.initialize()
    record = SatisfactionRecord(
        star_name=STAR_NAME,
        content_digest=CONTENT_DIGEST,
        verdict="useful",
        created_at="2026-08-14T17:00:00Z",
        envelope_id="env-restart-1",
        note="kept",
        caller_namespace="agents/demo",
    )
    first.put(record)

    restarted = PostgresSatisfactionStore(lambda: _Connection(backend))
    fetched = restarted.get_for_receipt(
        content_digest=CONTENT_DIGEST,
        envelope_id="env-restart-1",
        call_attempt_id=None,
    )
    assert fetched is not None
    assert fetched.receipt_key() == record.receipt_key()
    assert fetched.verdict == "useful"
    assert fetched.note == "kept"
    assert fetched.caller_namespace == "agents/demo"


@pytest.mark.issue(459)
def test_postgres_digest_change_does_not_rewrite_old_verdicts() -> None:
    backend = _RowStore()
    store = PostgresSatisfactionStore(lambda: _Connection(backend))
    store.initialize()
    old_digest = "sha256:old-digest"
    live_digest = "sha256:live-digest"
    store.put(
        SatisfactionRecord(
            star_name=STAR_NAME,
            content_digest=old_digest,
            verdict="stale",
            created_at="2026-08-14T17:00:00Z",
            envelope_id="env-same-authority",
        )
    )
    store.put(
        SatisfactionRecord(
            star_name=STAR_NAME,
            content_digest=live_digest,
            verdict="useful",
            created_at="2026-08-14T18:00:00Z",
            envelope_id="env-same-authority",
        )
    )

    historical = store.get_for_receipt(
        content_digest=old_digest,
        envelope_id="env-same-authority",
        call_attempt_id=None,
    )
    assert historical is not None
    assert historical.verdict == "stale"

    old_agg = store.aggregate(star_name=STAR_NAME, content_digest=old_digest)
    live_agg = store.aggregate(star_name=STAR_NAME, content_digest=live_digest)
    assert old_agg.counts == {"stale": 1}
    assert live_agg.counts == {"useful": 1}
    assert old_agg.total == 1
    assert live_agg.total == 1


@pytest.mark.issue(459)
def test_postgres_adapter_fail_closed_without_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SatisfactionStoreUnavailable, match="DATABASE_URL"):
        PostgresSatisfactionStore()


@pytest.mark.issue(459)
def test_rate_listing_without_database_url_is_store_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("trust.satisfaction._default_store", None)
    result = submit_rate(
        star_name=STAR_NAME,
        content_digest=CONTENT_DIGEST,
        verdict="useful",
        call_attempt_id="attempt-no-store",
        verify_receipt=verify_receipt,
    )
    assert result["status"] == "rejected"
    assert result["error"] == "store_unavailable"


@pytest.mark.issue(459)
def test_factory_selects_postgres_when_database_url_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _RowStore()
    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.setattr("trust.satisfaction._default_store", None)
    monkeypatch.setattr("psycopg.connect", lambda _url: _Connection(backend))

    store = get_satisfaction_store()
    assert isinstance(store, PostgresSatisfactionStore)
    store.put(
        SatisfactionRecord(
            star_name=STAR_NAME,
            content_digest=CONTENT_DIGEST,
            verdict="broken",
            created_at="2026-08-14T17:00:00Z",
            call_attempt_id="factory-1",
        )
    )
    assert get_satisfaction_store() is store
    fetched = store.get_for_receipt(
        content_digest=CONTENT_DIGEST,
        envelope_id=None,
        call_attempt_id="factory-1",
    )
    assert fetched is not None
    assert fetched.verdict == "broken"


class _RowStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], tuple[object, ...]] = {}


class _Cursor:
    def __init__(self, backend: _RowStore) -> None:
        self._backend = backend
        self._row: tuple[object, ...] | None = None
        self._rows: list[tuple[object, ...]] = []

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        sql = " ".join(query.split()).upper()
        if "CREATE TABLE" in sql or "CREATE INDEX" in sql:
            return
        if sql.startswith("INSERT"):
            key = (str(params[0]), str(params[1]))
            self._backend.rows[key] = params
            self._row = params
            return
        if "GROUP BY" in sql:
            star_name, content_digest, _since_flag, since = params
            counts: dict[str, int] = {}
            for row in self._backend.rows.values():
                if row[3] != star_name or row[0] != content_digest:
                    continue
                if since is not None and str(row[7]) < str(since):
                    continue
                verdict = str(row[4])
                counts[verdict] = counts.get(verdict, 0) + 1
            self._rows = [(verdict, total) for verdict, total in sorted(counts.items())]
            return
        if "AUTHORITY_ID" in sql:
            self._row = self._backend.rows.get((str(params[0]), str(params[1])))
            return
        self._rows = [row for row in self._backend.rows.values() if row[3] == params[0]]

    def fetchone(self) -> tuple[object, ...] | None:
        if self._rows:
            return self._rows.pop(0)
        return self._row

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)

    def close(self) -> None:
        return None


class _Connection:
    def __init__(self, backend: _RowStore) -> None:
        self._backend = backend

    def cursor(self) -> _Cursor:
        return _Cursor(self._backend)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None
