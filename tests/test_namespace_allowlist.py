"""Namespace caller allowlists + retention hooks (#30)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from namespaces import CALLER_HEADER, get_namespace, reset_namespace_store, retention_days_for

pytestmark = pytest.mark.issue(30)


@pytest.fixture
def allowlist_app(example_app):
    """Fresh namespace registry for each test."""
    reset_namespace_store()
    yield example_app
    reset_namespace_store()


async def _provision(
    client,
    *,
    namespace_id: str = "acme",
    retention_days: int | None = None,
    caller_allowlist: list[str] | None = None,
) -> dict:
    payload: dict[str, object] = {"id": namespace_id}
    if retention_days is not None:
        payload["retention_days"] = retention_days
    if caller_allowlist is not None:
        payload["caller_allowlist"] = caller_allowlist
    response = await client.post("/api/namespaces", json=payload)
    return {"status": response.status, "body": json.loads(response.text)}


@pytest.mark.issue(30)
async def test_provision_accepts_retention_and_allowlist(allowlist_app) -> None:
    async with TestClient(allowlist_app) as client:
        result = await _provision(
            client,
            namespace_id="widgetco",
            retention_days=30,
            caller_allowlist=["agent:deploy", "agent:ci"],
        )
    assert result["status"] == 201
    assert result["body"]["retention_days"] == 30
    assert result["body"]["caller_allowlist"] == ["agent:deploy", "agent:ci"]
    record = get_namespace("widgetco")
    assert record is not None
    assert retention_days_for("widgetco") == 30


@pytest.mark.issue(30)
async def test_empty_allowlist_leaves_private_paths_open(allowlist_app) -> None:
    async with TestClient(allowlist_app) as client:
        await _provision(client, namespace_id="acme", caller_allowlist=[])
        response = await client.get("/api/resolve?name=acme/release-gate")
    assert response.status == 200


@pytest.mark.issue(30)
async def test_non_empty_allowlist_denies_unauthorized_resolve(allowlist_app) -> None:
    async with TestClient(allowlist_app) as client:
        await _provision(client, caller_allowlist=["agent:deploy"])
        denied = await client.get("/api/resolve?name=acme/release-gate")
        allowed = await client.get(
            "/api/resolve?name=acme/release-gate",
            headers={CALLER_HEADER: "agent:deploy"},
        )
    assert denied.status == 403
    assert json.loads(denied.text)["error"] == "caller_not_allowed"
    assert allowed.status == 200


@pytest.mark.issue(30)
async def test_non_empty_allowlist_denies_unauthorized_gaze_node(allowlist_app) -> None:
    async with TestClient(allowlist_app) as client:
        await _provision(client, caller_allowlist=["agent:deploy"])
        denied = await client.get("/api/gaze/search?q=release&node=acme")
        allowed = await client.get(
            "/api/gaze/search?q=release&node=acme",
            headers={CALLER_HEADER: "agent:deploy"},
        )
    assert denied.status == 403
    assert allowed.status == 200


@pytest.mark.issue(30)
async def test_public_resolve_and_gaze_unaffected(allowlist_app) -> None:
    async with TestClient(allowlist_app) as client:
        await _provision(client, caller_allowlist=["agent:deploy"])
        resolve = await client.get("/api/resolve?name=orrery/world-time")
        gaze = await client.get("/api/gaze/search?q=time&node=public")
    assert resolve.status == 200
    assert gaze.status == 200


@pytest.mark.issue(30)
async def test_invalid_retention_or_allowlist_returns_400(allowlist_app) -> None:
    async with TestClient(allowlist_app) as client:
        bad_days = await client.post(
            "/api/namespaces",
            json={"id": "acme", "retention_days": 0},
        )
        bad_allowlist = await client.post(
            "/api/namespaces",
            json={"id": "widgetco", "caller_allowlist": ["", "agent:a"]},
        )
    assert bad_days.status == 400
    assert json.loads(bad_days.text)["error"] == "invalid_retention_days"
    assert bad_allowlist.status == 400
    assert json.loads(bad_allowlist.text)["error"] == "invalid_caller_allowlist"
