"""Namespace provisioner store + POST /api/namespaces (#382) + HTML form (#476)."""

from __future__ import annotations

import json
import re

import pytest
from chirp.testing import TestClient

from catalog import CATALOG
from catalog.gaze import records_for_gaze_node
from namespaces import reset_namespace_store

_CSRF_RE = re.compile(r'name="_csrf_token" value="([^"]+)"')


def _session_cookie(response) -> str:
    raw = response.header("Set-Cookie")
    assert raw, "expected chirp session cookie"
    return raw.split(";", 1)[0]


def _csrf_token(html: str) -> str:
    match = _CSRF_RE.search(html)
    assert match, "expected csrf_field on the namespace form"
    return match.group(1)


async def _form_session(client: TestClient) -> tuple[str, str]:
    page = await client.get("/namespaces")
    assert page.status == 200
    return _session_cookie(page), _csrf_token(page.text)


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
@pytest.mark.issue(476)
async def test_namespace_page_maps_known_error_copy(provision_app) -> None:
    from pages.namespaces._errors import KNOWN

    samples = {
        "invalid_slug": "1bad",
        "reserved_slug": "orrery",
        "duplicate_namespace": "acme",
    }
    async with TestClient(provision_app) as client:
        cookie, token = await _form_session(client)
        await client.post("/api/namespaces", json={"id": "acme"})
        for code, slug in samples.items():
            copy = KNOWN[code]
            response = await client.post(
                "/namespaces",
                data={"id": slug, "_csrf_token": token},
                headers={"Cookie": cookie},
            )
            assert response.status == 303
            location = response.header("Location")
            assert location
            assert f"error={code}" in location
            landed = await client.get(location, headers={"Cookie": cookie})
            assert landed.status == 200
            assert copy["message"] in landed.text
            assert copy["next"] in landed.text
            assert code in landed.text
            assert 'class="alert"' in landed.text
            assert 'role="alert"' in landed.text
    assert "this.error = body.error" not in landed.text
    assert "createNamespace" not in landed.text
    assert 'id="namespace-error-map"' not in landed.text


@pytest.mark.issue(476)
async def test_namespace_form_post_redirects_without_js(provision_app) -> None:
    async with TestClient(provision_app) as client:
        cookie, token = await _form_session(client)
        response = await client.post(
            "/namespaces",
            data={"id": "widgetco", "_csrf_token": token},
            headers={"Cookie": cookie},
        )
        assert response.status == 303
        location = response.header("Location")
        assert location == "/namespaces?created=widgetco"
        landed = await client.get(location, headers={"Cookie": cookie})
    assert landed.status == 200
    assert "widgetco" in landed.text
    assert "/gaze?node=widgetco" in landed.text
    assert "/resolve?name=widgetco/demo" in landed.text
    assert "createNamespace" not in landed.text


@pytest.mark.issue(476)
async def test_namespace_form_htmx_fragment_busy_and_alert(provision_app) -> None:
    async with TestClient(provision_app) as client:
        cookie, token = await _form_session(client)
        error = await client.post(
            "/namespaces",
            data={"id": "orrery", "_csrf_token": token},
            headers={"Cookie": cookie, "HX-Request": "true"},
        )
        assert error.status == 422
        assert "That id is reserved." in error.text
        assert 'class="alert"' in error.text
        assert "reserved_slug" in error.text
        assert "htmx-indicator" in error.text
        assert "Create namespace" in error.text
        assert "<html" not in error.text.lower()

        ok = await client.post(
            "/namespaces",
            data={"id": "widgetco", "_csrf_token": token},
            headers={"Cookie": cookie, "HX-Request": "true"},
        )
    assert ok.status == 200
    assert "widgetco" in ok.text
    assert "/gaze?node=widgetco" in ok.text
    assert "<html" not in ok.text.lower()
