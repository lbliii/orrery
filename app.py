"""Orrery — skills you point at, not install.

The product surfaces (Gaze, Resolve, Stars, Constellations, Namespaces) live in
``pages/`` via Chirp filesystem routing (``mount_pages``) and match the frozen
``v1-night-gold`` design mocks. Resolve records ("Skill DNS") come from the
in-memory :mod:`catalog`.

The same process is also a dogfood MCP host: it wraps N ``chirp.skill`` apps via
``mount_skills`` onto one aggregated ``/mcp``, exposes discovery at ``/skills``,
and a hypermedia console at ``/console``. The landing page's live feed bridges
``ToolEventBus`` → ``EventStream`` so agent invocations appear in real time.

See the backlog at https://github.com/lbliii/orrery/issues/1.

Run locally::

    uv run python app.py

Point an MCP client at ``/mcp``. Open ``/`` for the brand + live feed,
``/resolve`` for the resolver console, ``/connect`` for agent onboarding,
or footer **Ops · console** for host reliability scores.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from chirp import (
    App,
    AppConfig,
    EventStream,
    Fragment,
    JSONResponse,
    Request,
    secure_stack,
)
from chirp.http.response import Response
from chirp.middleware.csrf import CSRFConfig
from chirp.middleware.security_headers import SecurityHeadersConfig
from chirp.skill import (
    ReliabilityStore,
    mount_console,
    mount_skills,
)
from chirp.skill.publish import run_publish_gate
from chirp.skill.smoke import render_faithful_answer

from catalog import CATALOG
from catalog.sync import refresh_catalog
from commerce import charge_on_verify, refund_on_forge
from discovery import (
    DISCOVERY_CACHE_CONTROL,
    DISCOVERY_CORS,
    configured_public_origin,
    llms_full_txt,
    llms_txt,
    mcp_manifest,
    resolve_public_origin,
    robots_txt,
    security_txt,
    server_card,
)
from discovery import (
    dumps as discovery_dumps,
)
from dogfood import DOGFOOD_CORPUS, build_dogfood_skills, verify_receipt
from mcp_compat import StandardMcpCompatibilityMiddleware
from public_keys import KEY_SET_CACHE_CONTROL, key_set_url, public_key_set
from stars._core.corpus import corpus_ok_by_star, validate_public_star_corpora
from stars._core.direct_mcp import mount_direct_mcp
from stars.builtins import build_direct_skills, builtin_registry
from stars.html_to_pdf.artifacts import ArtifactDeliveryUnavailable, get_pdf_artifacts
from trust.oracle import configure_oracle, record_skill_scores_from_registry

_ROOT = Path(__file__).parent
PAGES_DIR = _ROOT / "pages"
STATIC_DIR = _ROOT / "static"

# Default secure_stack CSP allows CDN scripts but NOT inline <style>, style=, or
# fonts.googleapis.com — which blanked the branded pages in production. Keep
# scripts host-allowlisted; permit inline CSS (mock parity) + Google Fonts.
# 'unsafe-eval' is required for the standard Alpine.js build used on /gaze.
_ORRERY_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "base-uri 'self'; frame-ancestors 'none'; object-src 'none'"
)

_DEFAULT_SECRET = "change-me-before-deploying"
_secret = os.environ.get("CHIRP_SECRET_KEY", _DEFAULT_SECRET)
_env = os.environ.get("CHIRP_ENV", "development")
_debug = os.environ.get("CHIRP_DEBUG", "1" if _env != "production" else "0") not in (
    "0",
    "false",
    "False",
    "",
)

config = AppConfig.from_env(
    secret_key=_secret,
    env=_env,
    debug=_debug,
    template_dir=PAGES_DIR,
    static_dir=STATIC_DIR,
    worker_mode="async",
)
app = App(config=config)
star_registry = builtin_registry()
direct_star_skills = build_direct_skills(star_registry)
_DIRECT_STAR_MCP_PATHS = frozenset(definition.direct_mcp_path for definition in star_registry)

if config.env != "development" and config.secret_key == _DEFAULT_SECRET:
    msg = (
        "Refusing to start in production with default secret key. "
        "Set CHIRP_SECRET_KEY to a strong random value."
    )
    raise RuntimeError(msg)

for middleware in secure_stack(
    app.config,
    # MCP JSON-RPC clients have no browser CSRF cookie; exempt the machine face.
    csrf=CSRFConfig(
        exempt_paths=frozenset({"/mcp", "/api/envelope/verify", *_DIRECT_STAR_MCP_PATHS})
    ),
    headers=SecurityHeadersConfig(content_security_policy=_ORRERY_CSP),
):
    app.add_middleware(middleware)

# MCP 2025-06-18 uses only the protocol header plus standard JSON-RPC body
# fields.  Chirp's current routing extension needs internal copies of those
# fields, supplied by this boundary without changing the public wire contract.
app.add_middleware(
    StandardMcpCompatibilityMiddleware({"/mcp", *_DIRECT_STAR_MCP_PATHS}), priority=1
)


# ---------------------------------------------------------------------------
# Dogfood skills → aggregated /mcp + discovery + console
# ---------------------------------------------------------------------------

_skills = build_dogfood_skills()
registry = mount_skills(app, _skills)
scores = ReliabilityStore()
mount_console(app, registry, scores=scores)

# Every Star also has a direct MCP endpoint with its canonical tool names.
# The aggregate host retains legacy aliases where flat MCP names collide.
for _definition in star_registry:
    mount_direct_mcp(app, _definition, direct_star_skills[_definition.name])

# ---------------------------------------------------------------------------
# Product surfaces → filesystem-routed pages (Gaze / Resolve / Stars / …)
# ---------------------------------------------------------------------------

app.mount_pages(str(PAGES_DIR))


# ---------------------------------------------------------------------------
# Public agent discovery (llms.txt, MCP well-known, robots, security)
# ---------------------------------------------------------------------------


def _orrery_origin(request: Request) -> str:
    return resolve_public_origin(configured_public_origin(), request.url)


def _discovery_json(payload: dict) -> Response:
    return Response(
        discovery_dumps(payload),
        content_type="application/json; charset=utf-8",
        headers=(
            ("Cache-Control", DISCOVERY_CACHE_CONTROL),
            ("Access-Control-Allow-Origin", DISCOVERY_CORS),
            ("X-Content-Type-Options", "nosniff"),
        ),
    )


def _discovery_text(body: str, *, content_type: str) -> Response:
    return Response(
        body if body.endswith("\n") else f"{body}\n",
        content_type=content_type,
        headers=(
            ("Cache-Control", DISCOVERY_CACHE_CONTROL),
            ("Access-Control-Allow-Origin", DISCOVERY_CORS),
            ("X-Content-Type-Options", "nosniff"),
        ),
    )


@app.route("/.well-known/mcp/server-card.json")
def mcp_server_card(request: Request) -> Response:
    return _discovery_json(server_card(_orrery_origin(request)))


@app.route("/.well-known/orrery/keys.json")
def envelope_public_keys(request: Request) -> Response:
    """JWKS-like public keys for independently verifying Star Envelopes."""
    return Response(
        discovery_dumps(public_key_set(direct_star_skills, origin=_orrery_origin(request))),
        content_type="application/json; charset=utf-8",
        headers=(
            ("Cache-Control", KEY_SET_CACHE_CONTROL),
            ("Access-Control-Allow-Origin", DISCOVERY_CORS),
            ("X-Content-Type-Options", "nosniff"),
        ),
    )


@app.route("/.well-known/mcp")
def mcp_well_known_manifest(request: Request) -> Response:
    return _discovery_json(mcp_manifest(_orrery_origin(request)))


@app.route("/.well-known/mcp.json")
def mcp_well_known_manifest_alias(request: Request) -> Response:
    # Early clients sometimes probe .json; same body as /.well-known/mcp.
    return _discovery_json(mcp_manifest(_orrery_origin(request)))


@app.route("/.well-known/security.txt")
def well_known_security(request: Request) -> Response:
    return _discovery_text(
        security_txt(_orrery_origin(request)),
        content_type="text/plain; charset=utf-8",
    )


@app.route("/llms.txt")
def llms_document(request: Request) -> Response:
    return _discovery_text(
        llms_txt(_orrery_origin(request)),
        content_type="text/plain; charset=utf-8",
    )


@app.route("/llms-full.txt")
def llms_full_document(request: Request) -> Response:
    return _discovery_text(
        llms_full_txt(_orrery_origin(request)),
        content_type="text/plain; charset=utf-8",
    )


@app.route("/robots.txt")
def robots_document(request: Request) -> Response:
    return _discovery_text(
        robots_txt(_orrery_origin(request)),
        content_type="text/plain; charset=utf-8",
    )


@app.template_filter("format_args")
def format_args(args: dict) -> str:
    """Format tool-call arguments for the live activity feed."""
    if not args:
        return "—"
    parts = []
    for key, value in args.items():
        parts.append(f'{key}="{value}"' if isinstance(value, str) else f"{key}={value}")
    return ", ".join(parts)


@app.template_filter("format_call_time")
def format_call_time(timestamp: float) -> str:
    """Format a unix timestamp for the live activity feed."""
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%H:%M:%S")


@app.route("/feed", referenced=True)
def feed():
    """Stream tool-call events so agent invocations appear on the landing feed."""

    async def generate():
        async for event in app.tool_events.subscribe():
            yield Fragment("_feed.html", "activity_row", event=event)

    return EventStream(generate())


@app.route("/api/resolve", referenced=True)
def api_resolve(request: Request) -> JSONResponse:
    """Skill DNS lookup: ``?name=`` → resolve record JSON, or 404."""
    name = (request.query.get("name") or "").strip()
    record = CATALOG.resolve(name) if name else None
    if record is None:
        return JSONResponse.from_value({"error": "not_found", "name": name}, status=404)
    payload = record.as_dict()
    payload["public_key_url"] = key_set_url(_orrery_origin(request))
    return JSONResponse.from_value(payload)


@app.route("/api/gaze/match", referenced=True)
def api_gaze_match(request: Request) -> JSONResponse:
    """Gaze match: ``?intent=`` (+ optional ``?node=`` / ``?limit=``) → bounded hits.

    Default shortlist cap is 20; explicit ``limit`` may raise up to 100.
    Agent is the semantic router — Orrery does not force a single winner.
    """
    from catalog.gaze import clamp_gaze_limit

    intent = (request.query.get("intent") or request.query.get("q") or "").strip()
    node = (request.query.get("node") or "public").strip() or "public"
    raw_limit = request.query.get("limit")
    limit: int | None
    if raw_limit is None or str(raw_limit).strip() == "":
        limit = None
    else:
        try:
            limit = int(str(raw_limit).strip())
        except ValueError:
            limit = None
    cap = clamp_gaze_limit(limit)
    if node == "docs":
        hits = CATALOG.hits_for_node("docs", limit=cap)
    else:
        hits = (
            CATALOG.match(intent, node=node, limit=cap)
            if intent
            else CATALOG.hits_for_node(node, limit=cap)
        )
    return JSONResponse.from_value(
        {
            "intent": intent,
            "node": node,
            "limit": len(hits),
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
            "note": "Agent is the semantic router; re-rank or filter by facets.",
        }
    )


@app.route("/api/gaze/search", referenced=True)
def api_gaze_search(request: Request) -> JSONResponse:
    """Gaze search: ``?q=`` (+ optional ``?node=`` / ``?limit=``) → bounded hits."""
    from catalog.gaze import clamp_gaze_limit

    query = (request.query.get("q") or request.query.get("query") or "").strip()
    node_raw = (request.query.get("node") or "").strip()
    node = node_raw or None
    raw_limit = request.query.get("limit")
    if raw_limit is None or str(raw_limit).strip() == "":
        limit = None
    else:
        try:
            limit = int(str(raw_limit).strip())
        except ValueError:
            limit = None
    cap = clamp_gaze_limit(limit)
    hits = CATALOG.search(query, node=node, limit=cap)
    return JSONResponse.from_value(
        {
            "query": query,
            "node": node,
            "limit": len(hits),
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
            "note": "Agent is the semantic router; re-rank or filter by facets.",
        }
    )


@app.route("/artifacts/{artifact_id}", referenced=True)
def pdf_artifact(artifact_id: str) -> Response:
    """Download a short-lived PDF emitted by the html-to-pdf Star."""
    try:
        delivered = get_pdf_artifacts().download(artifact_id)
    except ArtifactDeliveryUnavailable:
        return Response(
            "PDF artifact delivery is temporarily unavailable.",
            status=503,
            content_type="text/plain; charset=utf-8",
            headers=(("Cache-Control", "no-store"),),
        )
    if delivered is None:
        return Response(
            "PDF artifact not found or expired.",
            status=404,
            content_type="text/plain; charset=utf-8",
        )
    artifact, data = delivered
    return Response(
        data,
        content_type="application/pdf",
        headers=(
            ("Content-Disposition", f'attachment; filename="{artifact.artifact_id}.pdf"'),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ),
    )


def _commerce_fields(body: dict) -> tuple[str | None, str | None]:
    """Pull payment + price from a receipt body (catalog fallback for price)."""
    payment_id = body.get("payment_id")
    if payment_id is not None:
        payment_id = str(payment_id)
    price = body.get("price_per_call")
    if price is None and isinstance(body.get("skill"), str):
        skill_name = body["skill"]
        record = CATALOG.resolve(skill_name) or CATALOG.resolve(f"orrery/{skill_name}")
        if record is not None:
            price = record.price_per_call
    if price is not None:
        price = str(price)
    return payment_id, price


@app.route("/api/envelope/verify", methods=["POST"], referenced=True)
async def api_envelope_verify(request: Request) -> JSONResponse:
    """Verify a Chirp Envelope / star receipt dict (fails closed on tamper).

    Success → loud ``commerce.charge_stub``; failure → loud ``commerce.refund_stub``.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse.from_value({"verified": False, "error": "invalid_json"}, status=400)
    if not isinstance(body, dict):
        return JSONResponse.from_value({"verified": False, "error": "expected_object"}, status=400)
    payment_id, price_per_call = _commerce_fields(body)
    # payment_id / price_per_call are commerce metadata, not Envelope wire fields.
    payload = {k: v for k, v in body.items() if k not in ("payment_id", "price_per_call")}
    ok = verify_receipt(payload)
    skill = str(body["skill"]) if isinstance(body.get("skill"), str) else None
    nonce = str(body["nonce"]) if isinstance(body.get("nonce"), str) else None
    if ok:
        commerce = charge_on_verify(
            payment_id=payment_id,
            price_per_call=price_per_call,
            skill=skill,
            nonce=nonce,
        )
    else:
        commerce = refund_on_forge(
            payment_id=payment_id,
            price_per_call=price_per_call,
            skill=skill,
            nonce=nonce,
        )
    return JSONResponse.from_value(
        {
            "verified": ok,
            "payment_id": payment_id,
            "price_per_call": price_per_call,
            "commerce": commerce,
        }
    )


# Publish-oracle dogfood: seed Skill DNS, then check → freeze → smoke with
# per-skill score slices. Skip with ORRERY_SKIP_PUBLISH=1 (async pytest).
# L1 (#117): every public star package must ship a non-empty CORPUS unless skip.
_publish_receipt = None
_corpus_ok = corpus_ok_by_star(star_registry)
if os.environ.get("ORRERY_SKIP_PUBLISH", "").strip() not in ("1", "true", "True"):
    validate_public_star_corpora(star_registry)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Public stars must exist before gaze/resolve smoke prompts run.
        refresh_catalog(star_registry, direct_star_skills, receipt=None)
        _publish_receipt = run_publish_gate(
            app,
            DOGFOOD_CORPUS,
            answer_fn=render_faithful_answer,
        )
        if _publish_receipt.smoke is not None:
            record_skill_scores_from_registry(scores, _publish_receipt.smoke, registry)

configure_oracle(receipt=_publish_receipt, scores=scores, corpus_ok=_corpus_ok)
# Re-sync digests / oracle_ok (and seed stars when publish was skipped).
refresh_catalog(star_registry, direct_star_skills, receipt=_publish_receipt)


if __name__ == "__main__":
    app.run()
