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
    Page,
    Request,
    secure_stack,
)
from chirp.http.response import Response
from chirp.middleware.csrf import CSRFConfig
from chirp.middleware.security_headers import SecurityHeadersConfig
from chirp.skill import (
    ReliabilityStore,
    SkillRegistry,
    mount_console,
)
from chirp.skill.smoke import render_faithful_answer

from artifacts import safe_attachment_filename
from catalog import CATALOG
from catalog.call_skill_proxy import register_publisher_registry
from catalog.coverage import check_coverage, coverage_index, describe_coverage
from catalog.sync import refresh_catalog
from commerce import (
    HoldRequestError,
    InsufficientBalanceError,
    WalletDisabledError,
    charge_on_verify,
    create_checkout_session,
    handle_stripe_webhook,
    open_hold,
    refund_on_forge,
)
from discovery import (
    DISCOVERY_CACHE_CONTROL,
    DISCOVERY_CORS,
    MCP_PROTOCOL_VERSION,
    TRUST_FACTS,
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
from dogfood import (
    DOGFOOD_CORPUS,
    DOGFOOD_MCP_PATH,
    build_discovery_skills,
    build_dogfood_call_skills,
    build_dogfood_skills,
    mount_orrery_skills,
    run_dogfood_publish_gate,
    verify_receipt,
)
from listings.ping import ping_listing
from listings.schema import ListingError
from listings.store import boot_durable_listings, load_allowlist_fixtures
from namespaces import (
    CALLER_HEADER,
    ProvisionError,
    authorize_private_namespace,
    authorize_private_record,
    caller_from_header,
    is_private_namespace_node,
    provision_namespace,
)
from public_keys import KEY_SET_CACHE_CONTROL, key_set_url, public_key_set
from sky import SkyVitalsStore, attach_vitals_to_tool_events
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
    mcp_connect_default=MCP_PROTOCOL_VERSION,
)
app = App(config=config)
sky_vitals = SkyVitalsStore()
attach_vitals_to_tool_events(app, sky_vitals)
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
        exempt_paths=frozenset({
            "/mcp",
            DOGFOOD_MCP_PATH,
            "/api/envelope/verify",
            "/api/wallet/hold",
            "/api/wallet/stripe/checkout",
            "/api/wallet/stripe/webhook",
            "/api/namespaces",
            "/api/listings/ping",
            *_DIRECT_STAR_MCP_PATHS,
        })
    ),
    headers=SecurityHeadersConfig(content_security_policy=_ORRERY_CSP),
):
    app.add_middleware(middleware)


# ---------------------------------------------------------------------------
# Dogfood skills — slim /mcp + labeled /mcp/dogfood + discovery + console
# ---------------------------------------------------------------------------

_skill_registry = SkillRegistry()
for _skill in build_dogfood_skills():
    _skill_registry.add(_skill)
_dogfood_mcp = mount_orrery_skills(
    app,
    registry=_skill_registry,
    discovery_skills=build_discovery_skills(),
    call_skills=build_dogfood_call_skills(),
)
registry = _skill_registry
scores = ReliabilityStore()
mount_console(app, registry, scores=scores)

# Every Star also has a direct MCP endpoint with its canonical tool names.
# The aggregate host retains legacy aliases where flat MCP names collide.
for _definition in star_registry:
    _direct_registry = mount_direct_mcp(app, _definition, direct_star_skills[_definition.name])
    register_publisher_registry(_definition.direct_mcp_path, _direct_registry)

# ---------------------------------------------------------------------------
# Product surfaces → filesystem-routed pages (Gaze / Resolve / Stars / …)
# ---------------------------------------------------------------------------

app.mount_pages(str(PAGES_DIR))


@app.route("/star/{namespace}/{star}")
def canonical_star_page(request: Request, namespace: str, star: str) -> Page:
    """Human Star pages use the singular, namespaced canonical route."""
    from catalog.star_page import page_for_star

    return page_for_star(f"{namespace}/{star}", request=request)


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


@app.route("/.well-known/orrery/agent-card.schema.json")
def agent_card_schema(request: Request) -> Response:
    """JSON Schema for versioned Agent Cards (#217)."""
    from catalog.agent_card import agent_card_json_schema

    return _discovery_json(agent_card_json_schema())


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


@app.route("/.well-known/orrery/trust.json")
def trust_document(request: Request) -> Response:
    origin = _orrery_origin(request)
    return _discovery_json(
        {
            "version": 1,
            "facts": TRUST_FACTS,
            "security": f"{origin}/.well-known/security.txt",
            "keys": f"{origin}/.well-known/orrery/keys.json",
            "allowlist": f"{origin}/trust/allowlist",
        }
    )


@app.route("/sitemap.xml")
def sitemap_document(request: Request) -> Response:
    origin = _orrery_origin(request)
    urls = ("/", "/security", "/privacy", "/terms", "/contact", "/trust/allowlist", "/connect")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{origin}{path}</loc></url>" for path in urls)
        + "</urlset>"
    )
    return Response(body, content_type="application/xml; charset=utf-8")


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


# Feed row polish — phase map frozen in docs/design/sky-vitals-homepage.md (#406).
_FEED_DISCOVER_TOOLS = frozenset(
    {
        "gaze_match",
        "gaze_search",
        "gaze_describe",
        "gaze_list_constellations",
        "coverage_check",
    }
)
_FEED_RESOLVE_TOOLS = frozenset({"resolve_name"})
_FEED_SEAL_TOOLS = frozenset({"explain_policy"})
_FEED_ARGS_DENYLIST = frozenset({"html", "body", "content", "note"})
_FEED_ARGS_MAX_LEN = 120
_FEED_CALL_TOOL_STARS: dict[str, str] = {
    "convert": "orrery/html-to-pdf",
    "fetch": "orrery/world-time",
    "get": "orrery/world-time",
    "source_watch_answer": "orrery/source-watch",
}


def feed_phase(tool_name: str) -> str:
    """Map an MCP tool name to a discover / resolve / call / seal phase."""
    if tool_name in _FEED_DISCOVER_TOOLS:
        return "discover"
    if tool_name in _FEED_RESOLVE_TOOLS:
        return "resolve"
    if tool_name in _FEED_SEAL_TOOLS:
        return "seal"
    return "call"


def _feed_star_from_name(name: str | None) -> tuple[str | None, str | None]:
    if not name:
        return None, None
    record = CATALOG.resolve(name)
    if record is None:
        return name, None
    return record.name, record.href


def feed_star_link(tool_name: str, args: dict) -> tuple[str | None, str | None]:
    """Return a resolved star name and detail href when the feed can infer one."""
    name = args.get("name")
    if isinstance(name, str) and name.strip():
        return _feed_star_from_name(name.strip())
    if tool_name in _FEED_CALL_TOOL_STARS:
        return _feed_star_from_name(_FEED_CALL_TOOL_STARS[tool_name])
    return None, None


def feed_display_line(tool_name: str, args: dict, star_name: str | None) -> str:
    """Human-readable feed copy — never the raw tool name alone."""
    if tool_name == "gaze_match":
        intent = args.get("intent")
        if isinstance(intent, str) and intent.strip():
            return f'Matching intent "{intent.strip()}"'
        return "Matching intent"
    if tool_name == "gaze_search":
        query = args.get("query")
        if isinstance(query, str) and query.strip():
            return f'Searching "{query.strip()}"'
        return "Searching catalog"
    if tool_name == "gaze_describe":
        return "Describing catalog entry"
    if tool_name == "gaze_list_constellations":
        return "Listing constellations"
    if tool_name == "coverage_check":
        return "Checking coverage"
    if tool_name == "resolve_name":
        target = star_name or args.get("name")
        if isinstance(target, str) and target.strip():
            return f"Resolved {target.strip()}"
        return "Resolved skill name"
    if tool_name == "explain_policy":
        target = star_name or args.get("name")
        if isinstance(target, str) and target.strip():
            return f"Policy for {target.strip()}"
        return "Explaining policy"
    if tool_name == "run":
        target = star_name or args.get("name")
        if isinstance(target, str) and target.strip():
            return f"Running {target.strip()}"
        return "Running constellation"
    if tool_name == "status":
        return "Checking run status"
    if star_name:
        short = star_name.split("/", 1)[-1]
        return f"Calling {short}"
    return f"Calling {tool_name.replace('_', ' ')}"


def feed_format_args(args: dict | None) -> str:
    """Format feed args with denylist and truncation (sky vitals #406)."""
    if not args:
        return ""
    parts: list[str] = []
    for key, value in args.items():
        if key in _FEED_ARGS_DENYLIST:
            continue
        if isinstance(value, str):
            parts.append(f'{key}="{value}"')
        else:
            parts.append(f"{key}={value}")
    if not parts:
        return ""
    rendered = ", ".join(parts)
    if len(rendered) <= _FEED_ARGS_MAX_LEN:
        return rendered
    return rendered[: _FEED_ARGS_MAX_LEN - 1].rstrip() + "…"


def feed_row_context(event) -> dict:
    """Build template context for one live invocation SSE row."""
    args = event.arguments if isinstance(event.arguments, dict) else {}
    star_name, star_href = feed_star_link(event.tool_name, args)
    return {
        "event": event,
        "phase": feed_phase(event.tool_name),
        "display_line": feed_display_line(event.tool_name, args, star_name),
        "star_name": star_name,
        "star_href": star_href,
        "formatted_args": feed_format_args(args),
    }


@app.template_filter("format_args")
def format_args(args: dict) -> str:
    """Format tool-call arguments for the live activity feed."""
    rendered = feed_format_args(args)
    return rendered or "—"


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
            yield Fragment("_feed.html", "activity_row", **feed_row_context(event))

    return EventStream(generate())


@app.route("/api/resolve", referenced=True)
def api_resolve(request: Request) -> JSONResponse:
    """Skill DNS lookup: ``?name=`` → resolve record JSON, or 404."""
    name = (request.query.get("name") or "").strip()
    record = CATALOG.resolve(name) if name else None
    if record is None:
        return JSONResponse.from_value({"error": "not_found", "name": name}, status=404)
    denied = authorize_private_record(
        record,
        caller_from_header(request.headers.get(CALLER_HEADER)),
    )
    if denied is not None:
        return JSONResponse.from_value(denied, status=403)
    payload = record.as_dict()
    payload["public_key_url"] = key_set_url(_orrery_origin(request))
    return JSONResponse.from_value(payload)


# ---------------------------------------------------------------------------
# Coverage — public allowlist preflight for agents (#221)
# Agent Cards (#217) link here via coverage_href; card schema is out of scope.
# ---------------------------------------------------------------------------


def _coverage_query_params(request: Request) -> dict[str, str]:
    """Flatten request query values to stripped strings."""
    params: dict[str, str] = {}
    for key in request.query:
        value = request.query.get(key)
        if value is None:
            continue
        params[str(key)] = str(value).strip()
    return params


@app.route("/coverage", referenced=True)
def api_coverage_index(_request: Request) -> JSONResponse:
    """List public allowlist-gated stars and known coverage gaps."""
    return JSONResponse.from_value(coverage_index())


@app.route("/coverage/{star_or_family}/check", referenced=True)
def api_coverage_check(request: Request, star_or_family: str) -> JSONResponse:
    """Membership check: ``?{param}=…`` → ``{allowed, reason}``."""
    result = check_coverage(star_or_family, params=_coverage_query_params(request))
    status = 404 if result.get("reason") == "unknown_star" else 200
    return JSONResponse.from_value(result, status=status)


@app.route("/coverage/{star_or_family}", referenced=True)
def api_coverage_describe(_request: Request, star_or_family: str) -> JSONResponse:
    """Allowlist metadata for one public star (entries + check href)."""
    payload = describe_coverage(star_or_family)
    if payload is None:
        return JSONResponse.from_value(
            {"error": "not_found", "star": star_or_family},
            status=404,
        )
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
    if is_private_namespace_node(node):
        denied = authorize_private_namespace(
            node,
            caller_from_header(request.headers.get(CALLER_HEADER)),
        )
        if denied is not None:
            return JSONResponse.from_value(denied, status=403)
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
    node = (request.query.get("node") or "public").strip() or "public"
    if is_private_namespace_node(node):
        denied = authorize_private_namespace(
            node,
            caller_from_header(request.headers.get(CALLER_HEADER)),
        )
        if denied is not None:
            return JSONResponse.from_value(denied, status=403)
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
def artifact_download(artifact_id: str) -> Response:
    """Proxy an authorized, non-expired artifact using its stored metadata."""
    try:
        delivered = get_pdf_artifacts().download(artifact_id)
    except ArtifactDeliveryUnavailable:
        return Response(
            "Artifact delivery is temporarily unavailable.",
            status=503,
            content_type="text/plain; charset=utf-8",
            headers=(("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff")),
        )
    if delivered is None:
        return Response(
            "Artifact not found, expired, or not authorized.",
            status=404,
            content_type="text/plain; charset=utf-8",
            headers=(("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff")),
        )
    artifact, data = delivered
    return Response(
        data,
        content_type=artifact.content_type,
        headers=(
            (
                "Content-Disposition",
                f'attachment; filename="{safe_attachment_filename(artifact.filename)}"',
            ),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ),
    )


def _commerce_fields(body: dict) -> tuple[str | None, str | None, str | None]:
    """Pull payment, price, and owner from a receipt body (catalog fallback for price)."""
    payment_id = body.get("payment_id")
    if payment_id is not None:
        payment_id = str(payment_id)
    owner_id = body.get("owner_id")
    if owner_id is not None:
        owner_id = str(owner_id)
    price = body.get("price_per_call")
    if price is None and isinstance(body.get("skill"), str):
        skill_name = body["skill"]
        record = CATALOG.resolve(skill_name) or CATALOG.resolve(f"orrery/{skill_name}")
        if record is not None:
            price = record.price_per_call
    if price is not None:
        price = str(price)
    return payment_id, price, owner_id


@app.route("/api/envelope/verify", methods=["POST"], referenced=True)
async def api_envelope_verify(request: Request) -> JSONResponse:
    """Verify a Chirp Envelope / star receipt dict (fails closed on tamper).

    Success → ledger capture (or loud stub when wallet disabled); failure → release.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse.from_value({"verified": False, "error": "invalid_json"}, status=400)
    if not isinstance(body, dict):
        return JSONResponse.from_value({"verified": False, "error": "expected_object"}, status=400)
    payment_id, price_per_call, owner_id = _commerce_fields(body)
    # Commerce metadata is not part of the Envelope wire signature.
    payload = {
        k: v
        for k, v in body.items()
        if k not in ("payment_id", "price_per_call", "owner_id")
    }
    ok = verify_receipt(payload)
    skill = str(body["skill"]) if isinstance(body.get("skill"), str) else None
    nonce = str(body["nonce"]) if isinstance(body.get("nonce"), str) else None
    if ok:
        commerce = charge_on_verify(
            payment_id=payment_id,
            price_per_call=price_per_call,
            skill=skill,
            nonce=nonce,
            owner_id=owner_id,
        )
    else:
        commerce = refund_on_forge(
            payment_id=payment_id,
            price_per_call=price_per_call,
            skill=skill,
            nonce=nonce,
            owner_id=owner_id,
        )
    response: dict[str, object] = {
        "verified": ok,
        "payment_id": payment_id,
        "price_per_call": price_per_call,
        "commerce": commerce,
    }
    if ok:
        sky_vitals.record_seal()
        signed_payload = payload.get("payload")
        if isinstance(signed_payload, dict):
            via = signed_payload.get("via")
            if isinstance(via, dict):
                line = via.get("line")
                sky = via.get("sky")
                if isinstance(line, str) and isinstance(sky, str):
                    response["via"] = {"line": line, "sky": sky}
    return JSONResponse.from_value(response)


@app.route("/api/sky/vitals", referenced=True)
def api_sky_vitals(_request: Request) -> JSONResponse:
    """Public host-truth sky metrics (anonymous, no-store)."""
    return JSONResponse.from_value(
        sky_vitals.snapshot(),
        headers={"Cache-Control": "no-store"},
    )


@app.route("/api/wallet/hold", methods=["POST"], referenced=True)
async def api_wallet_hold(request: Request) -> JSONResponse:
    """Open an idempotent prepaid hold before a publisher call (ADR 0002)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse.from_value({"error": "invalid_json"}, status=400)
    if not isinstance(body, dict):
        return JSONResponse.from_value({"error": "expected_object"}, status=400)

    owner_id = body.get("owner_id")
    if not isinstance(owner_id, str):
        return JSONResponse.from_value({"error": "owner_id_required"}, status=400)
    payment_id = body.get("payment_id")
    if not isinstance(payment_id, str):
        return JSONResponse.from_value({"error": "payment_id_required"}, status=400)

    price_per_call = body.get("price_per_call")
    if price_per_call is not None and not isinstance(price_per_call, str):
        return JSONResponse.from_value({"error": "invalid_price_per_call"}, status=400)
    if price_per_call is None and isinstance(body.get("skill"), str):
        skill_name = body["skill"]
        record = CATALOG.resolve(skill_name) or CATALOG.resolve(f"orrery/{skill_name}")
        if record is not None:
            price_per_call = record.price_per_call
    amount_cents = body.get("amount_cents")
    if amount_cents is not None and not isinstance(amount_cents, int):
        return JSONResponse.from_value({"error": "invalid_amount_cents"}, status=400)
    skill = body.get("skill")
    if skill is not None and not isinstance(skill, str):
        return JSONResponse.from_value({"error": "invalid_skill"}, status=400)

    try:
        result = open_hold(
            owner_id=owner_id,
            payment_id=payment_id,
            price_per_call=price_per_call,
            amount_cents=amount_cents,
            skill=skill,
        )
    except WalletDisabledError:
        return JSONResponse.from_value(
            {"error": "wallet_disabled", "wallet_enabled": False},
            status=503,
        )
    except HoldRequestError as exc:
        return JSONResponse.from_value({"error": exc.code}, status=400)
    except InsufficientBalanceError as exc:
        return JSONResponse.from_value(exc.to_dict(), status=402)
    return JSONResponse.from_value(result)


@app.route("/api/wallet/stripe/checkout", methods=["POST"], referenced=True)
async def api_wallet_stripe_checkout(request: Request) -> JSONResponse:
    """Create a Stripe Checkout Session with ``metadata.owner_id`` (ADR 0003)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse.from_value({"error": "invalid_json"}, status=400)
    if not isinstance(body, dict):
        return JSONResponse.from_value({"error": "expected_object"}, status=400)
    owner_id = body.get("owner_id")
    if not isinstance(owner_id, str) or not owner_id.strip():
        return JSONResponse.from_value({"error": "owner_id_required"}, status=400)
    pack = body.get("pack")
    if pack is not None and not isinstance(pack, str):
        return JSONResponse.from_value({"error": "invalid_pack"}, status=400)
    success_url = body.get("success_url")
    if success_url is not None and not isinstance(success_url, str):
        return JSONResponse.from_value({"error": "invalid_success_url"}, status=400)
    cancel_url = body.get("cancel_url")
    if cancel_url is not None and not isinstance(cancel_url, str):
        return JSONResponse.from_value({"error": "invalid_cancel_url"}, status=400)
    try:
        session = create_checkout_session(
            owner_id=owner_id.strip(),
            pack=pack,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as exc:
        return JSONResponse.from_value({"error": str(exc)}, status=400)
    except RuntimeError as exc:
        return JSONResponse.from_value({"error": str(exc)}, status=503)
    return JSONResponse.from_value(
        {
            "checkout_session_id": session.get("id"),
            "url": session.get("url"),
            "metadata": session.get("metadata"),
            "amount_total": session.get("amount_total"),
        }
    )


@app.route("/api/wallet/stripe/webhook", methods=["POST"], referenced=True)
async def api_wallet_stripe_webhook(request: Request) -> JSONResponse:
    """Verify Stripe webhook signature and credit the prepaid ledger once per event."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    status, body = handle_stripe_webhook(payload, signature_header=signature)
    return JSONResponse.from_value(body, status=status)


@app.route("/api/namespaces", methods=["POST"], referenced=True)
async def api_create_namespace(request: Request) -> JSONResponse:
    """Provision a private namespace id for gaze/resolve scoping (#29 / #382)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse.from_value({"error": "invalid_json"}, status=400)
    if not isinstance(body, dict):
        return JSONResponse.from_value({"error": "expected_object"}, status=400)
    raw_id = body.get("id")
    if not isinstance(raw_id, str):
        return JSONResponse.from_value({"error": "id_required"}, status=400)
    try:
        result = provision_namespace(
            raw_id,
            catalog=CATALOG,
            retention_days=body.get("retention_days"),
            caller_allowlist=body.get("caller_allowlist"),
        )
    except ProvisionError as exc:
        return JSONResponse.from_value({"error": exc.code}, status=400)
    return JSONResponse.from_value(result, status=201)


@app.route("/api/listings/ping", methods=["POST"], referenced=True)
async def api_listings_ping(request: Request) -> JSONResponse:
    """Fetch one submitted listing URL and land it in ``new/`` (ADR 0012)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse.from_value({"error": "invalid_json"}, status=400)
    if not isinstance(body, dict):
        return JSONResponse.from_value({"error": "expected_object"}, status=400)
    url = body.get("url")
    if not isinstance(url, str):
        return JSONResponse.from_value({"error": "url_required"}, status=400)
    try:
        record = ping_listing(url)
    except ListingError as exc:
        return JSONResponse.from_value({"error": exc.code}, status=400)
    return JSONResponse.from_value(
        {
            "name": record.name,
            "claimed_name": record.claimed_name,
            "index_tier": record.index_tier,
            "endpoint": record.endpoint,
            "oracle_ok": record.oracle_ok,
            "content_digest": record.content_digest,
        },
        status=201,
    )


# Publish-oracle dogfood: seed Skill DNS, then check → freeze → smoke with
# per-skill score slices. Skip with ORRERY_SKIP_PUBLISH=1 (async pytest).
# L1 (#117): every public star package must ship a non-empty CORPUS unless skip.
_publish_receipt = None
_corpus_ok = corpus_ok_by_star(star_registry)
boot_durable_listings()
load_allowlist_fixtures()
if os.environ.get("ORRERY_SKIP_PUBLISH", "").strip() not in ("1", "true", "True"):
    validate_public_star_corpora(star_registry)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Public stars must exist before gaze/resolve smoke prompts run.
        refresh_catalog(star_registry, direct_star_skills, receipt=None)
        _publish_receipt = run_dogfood_publish_gate(
            app,
            DOGFOOD_CORPUS,
            dogfood_registry=_dogfood_mcp,
            answer_fn=render_faithful_answer,
        )
        if _publish_receipt.smoke is not None:
            record_skill_scores_from_registry(scores, _publish_receipt.smoke, registry)

configure_oracle(receipt=_publish_receipt, scores=scores, corpus_ok=_corpus_ok)
# Re-sync digests / oracle_ok (and seed stars when publish was skipped).
refresh_catalog(star_registry, direct_star_skills, receipt=_publish_receipt)


if __name__ == "__main__":
    app.run()
