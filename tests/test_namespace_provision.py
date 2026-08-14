"""Namespace provisioner store + POST /api/namespaces (#382)."""

from __future__ import annotations

import json

import pytest
from chirp.testing import TestClient

from catalog import CATALOG
from catalog.gaze import records_for_gaze_node
from namespaces import reset_namespace_store


@pytest.fixture
def provision_app(example_app):
    """Fresh namespace registry for each test."""
    reset_namespace_store()
    yield example_app
    reset_namespace_store()


@pytest.mark.issue(382)
async def test_create_acme_returns_201(provision_app) -> None:
    async with TestClient(provision_app) as client:
        response = await client.post("/api/namespaces", json={"id": "acme"})
    assert response.status == 201
    body = json.loads(response.text)
    assert body["id"] == "acme"
    assert "created_at" in body
    assert body["retention_days"] == 90
    scoped = records_for_gaze_node(CATALOG.all(), "acme")
    assert scoped
    assert all(record.name.startswith("acme/") for record in scoped)


@pytest.mark.issue(382)
async def test_reserved_orrery_returns_400(provision_app) -> None:
    async with TestClient(provision_app) as client:
        response = await client.post("/api/namespaces", json={"id": "orrery"})
    assert response.status == 400
    assert json.loads(response.text)["error"] == "reserved_slug"


@pytest.mark.issue(382)
async def test_duplicate_namespace_returns_400(provision_app) -> None:
    async with TestClient(provision_app) as client:
        first = await client.post("/api/namespaces", json={"id": "acme"})
        second = await client.post("/api/namespaces", json={"id": "acme"})
    assert first.status == 201
    assert second.status == 400
    assert json.loads(second.text)["error"] == "duplicate_namespace"


@pytest.mark.issue(382)
async def test_invalid_slug_returns_400(provision_app) -> None:
    async with TestClient(provision_app) as client:
        for bad_id in ("1bad", "a", "bad_underscore", ""):
            response = await client.post("/api/namespaces", json={"id": bad_id})
            assert response.status == 400
            assert json.loads(response.text)["error"] == "invalid_slug"


@pytest.mark.issue(382)
async def test_new_namespace_seeds_demo_record(provision_app) -> None:
    async with TestClient(provision_app) as client:
        response = await client.post("/api/namespaces", json={"id": "widgetco"})
    assert response.status == 201
    record = CATALOG.resolve("widgetco/demo")
    assert record is not None
    assert record.visibility == "private"
    scoped = records_for_gaze_node(CATALOG.all(), "widgetco")
    assert any(r.name == "widgetco/demo" for r in scoped)


@pytest.mark.issue(433)
async def test_namespace_page_maps_known_error_copy(example_app) -> None:
    from pages.namespaces._errors import KNOWN

    async with TestClient(example_app) as client:
        response = await client.get("/namespaces")
    assert response.status == 200
    for code, copy in KNOWN.items():
        assert code in response.text
        assert copy["message"] in response.text
        assert copy["next"] in response.text
    assert "this.error = body.error" not in response.text
    assert 'x-text="errorCode"' in response.text
