"""Sky vitals store and GET /api/sky/vitals (#408)."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest
from chirp.testing import TestClient

from pages.page import public_capability_counts
from sky.storage import RedisStorage
from sky.vitals import SkyVitalsStore

_META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"

_REQUIRED_KEYS = (
    "generated_at",
    "catalog",
    "activity",
)
_ACTIVITY_KEYS = (
    "invocations_1h",
    "invocations_24h",
    "resolves_24h",
    "seals_24h",
    "last_invocation_at",
)


def _modern_mcp_params(**extra: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "_meta": {
            _META_PROTOCOL_VERSION: "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }
    params.update(extra)
    return params


def _modern_mcp_headers(method: str, name: str | None = None) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    return headers


def _vitals_store(example_app) -> SkyVitalsStore:
    host = sys.modules["orrery_app_under_test"]
    return host.sky_vitals


@pytest.mark.issue(408)
def test_rolling_window_expiry_prunes_old_events() -> None:
    now = 1_700_000_000.0
    store = SkyVitalsStore(clock=lambda: now)
    store.record_invocation("gaze_match", timestamp=now - 90_000)
    store.record_invocation("gaze_match", timestamp=now - 3_600)
    store.record_invocation("resolve_name", timestamp=now - 90_000)
    store.record_invocation("resolve_name", timestamp=now - 1_800)
    store.record_seal(timestamp=now - 90_000)
    store.record_seal(timestamp=now - 600)

    snapshot = store.snapshot()
    activity = snapshot["activity"]
    assert activity["invocations_24h"] == 2
    assert activity["invocations_1h"] == 2
    assert activity["resolves_24h"] == 1
    assert activity["seals_24h"] == 1


@pytest.mark.issue(408)
async def test_tool_events_increment_invocation_windows(example_app) -> None:
    store = _vitals_store(example_app)
    before = store.snapshot()["activity"]
    async with TestClient(example_app) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 4081,
                "params": _modern_mcp_params(
                    name="gaze_match",
                    arguments={"intent": "pdf convert", "node": "public"},
                ),
            },
            headers=_modern_mcp_headers("tools/call", "gaze_match"),
        )
        assert response.status == 200

    after = store.snapshot()["activity"]
    assert after["invocations_1h"] == before["invocations_1h"] + 1
    assert after["invocations_24h"] == before["invocations_24h"] + 1
    assert after["last_invocation_at"] is not None


@pytest.mark.issue(408)
async def test_resolve_name_increments_resolves_24h(example_app) -> None:
    store = _vitals_store(example_app)
    before = store.snapshot()["activity"]["resolves_24h"]
    async with TestClient(example_app) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 4082,
                "params": _modern_mcp_params(
                    name="resolve_name",
                    arguments={"name": "orrery/html-to-pdf"},
                ),
            },
            headers=_modern_mcp_headers("tools/call", "resolve_name"),
        )
        assert response.status == 200

    after = store.snapshot()["activity"]["resolves_24h"]
    assert after == before + 1


@pytest.mark.issue(408)
async def test_envelope_verify_success_increments_seals_24h(example_app) -> None:
    from dogfood import signed_convert_receipt

    store = _vitals_store(example_app)
    before = store.snapshot()["activity"]["seals_24h"]
    receipt, verified = signed_convert_receipt()
    assert verified is True

    async with TestClient(example_app) as client:
        ok = await client.post("/api/envelope/verify", json=receipt)
        assert ok.status == 200
        body = json.loads(ok.text)
        assert body["verified"] is True

        forged = dict(receipt)
        forged["nonce"] = "tampered-nonce"
        bad = await client.post("/api/envelope/verify", json=forged)
        assert bad.status == 200
        assert json.loads(bad.text)["verified"] is False

    after = store.snapshot()["activity"]["seals_24h"]
    assert after == before + 1


@pytest.mark.issue(408)
async def test_get_sky_vitals_returns_schema_and_no_store(example_app) -> None:
    star_count, constellation_count = public_capability_counts()
    async with TestClient(example_app) as client:
        response = await client.get("/api/sky/vitals")
        assert response.status == 200
        assert response.header("Cache-Control") == "no-store"
        body = json.loads(response.text)

    for key in _REQUIRED_KEYS:
        assert key in body
    assert set(body["activity"]) >= set(_ACTIVITY_KEYS)
    assert body["catalog"]["stars_live"] == star_count
    assert body["catalog"]["constellations_live"] == constellation_count
    assert body["demand"]["useful_7d"] == 0
    assert body["tenancy"]["namespaces_live"] == 0


class _FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | bytes | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


def _redis_store(clock: Any, fake: _FakeRedis) -> SkyVitalsStore:
    return SkyVitalsStore(clock=clock, storage=RedisStorage(fake))


@pytest.mark.issue(410)
def test_persist_counters_restored_after_store_reload() -> None:
    now = 1_700_000_000.0
    fake = _FakeRedis()
    clock = lambda: now  # noqa: E731

    store = _redis_store(clock, fake)
    store.record_invocation("gaze_match", timestamp=now - 600)
    store.record_invocation(
        "resolve_name",
        arguments={"name": "orrery/html-to-pdf"},
        timestamp=now - 300,
    )
    store.record_seal(timestamp=now - 120)

    reloaded = _redis_store(clock, fake)
    activity = reloaded.snapshot()["activity"]
    assert activity["invocations_24h"] == 2
    assert activity["resolves_24h"] == 1
    assert activity["seals_24h"] == 1


@pytest.mark.issue(410)
def test_top_resolved_7d_rollup_from_resolve_name_args() -> None:
    now = 1_700_000_000.0
    store = SkyVitalsStore(clock=lambda: now)

    store.record_invocation(
        "resolve_name",
        arguments={"name": "orrery/html-to-pdf"},
        timestamp=now - 3 * 86_400,
    )
    store.record_invocation(
        "resolve_name",
        arguments={"name": "orrery/html-to-pdf"},
        timestamp=now - 86_400,
    )
    store.record_invocation(
        "resolve_name",
        arguments={"name": "orrery/csv-url-allowlist"},
        timestamp=now - 86_400,
    )
    store.record_invocation(
        "resolve_name",
        arguments={"name": "orrery/stale-star"},
        timestamp=now - 8 * 86_400,
    )

    top = store.snapshot()["activity"]["top_resolved_7d"]
    assert top == [
        {"name": "orrery/html-to-pdf", "resolves": 2},
        {"name": "orrery/csv-url-allowlist", "resolves": 1},
    ]


@pytest.mark.issue(410)
def test_top_resolved_7d_caps_at_five_names() -> None:
    now = 1_700_000_000.0
    store = SkyVitalsStore(clock=lambda: now)

    for index in range(6):
        store.record_invocation(
            "resolve_name",
            arguments={"name": f"orrery/star-{index}"},
            timestamp=now - index * 60,
        )

    top = store.snapshot()["activity"]["top_resolved_7d"]
    assert len(top) == 5
    assert all(entry["resolves"] == 1 for entry in top)


@pytest.mark.issue(410)
def test_persist_degraded_mode_without_redis_is_in_process_only() -> None:
    now = 1_700_000_000.0
    clock = lambda: now  # noqa: E731

    first = SkyVitalsStore(clock=clock)
    first.record_invocation("gaze_match", timestamp=now - 600)

    second = SkyVitalsStore(clock=clock)
    assert second.snapshot()["activity"]["invocations_24h"] == 0
