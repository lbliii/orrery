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
``/resolve`` for the resolver console, or ``/console`` for reliability scores.
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
from chirp.middleware.csrf import CSRFConfig
from chirp.middleware.security_headers import SecurityHeadersConfig
from chirp.skill import (
    ReliabilityStore,
    mount_console,
    mount_skills,
)
from chirp.skill.smoke import render_faithful_answer, run_smoke

from catalog import CATALOG
from dogfood import DOGFOOD_CORPUS, build_dogfood_skills

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

if config.env != "development" and config.secret_key == _DEFAULT_SECRET:
    msg = (
        "Refusing to start in production with default secret key. "
        "Set CHIRP_SECRET_KEY to a strong random value."
    )
    raise RuntimeError(msg)

for middleware in secure_stack(
    app.config,
    # MCP JSON-RPC clients have no browser CSRF cookie; exempt the machine face.
    csrf=CSRFConfig(exempt_paths=frozenset({"/mcp"})),
    headers=SecurityHeadersConfig(content_security_policy=_ORRERY_CSP),
):
    app.add_middleware(middleware)


# ---------------------------------------------------------------------------
# Dogfood skills → aggregated /mcp + discovery + console
# ---------------------------------------------------------------------------

_skills = build_dogfood_skills()
registry = mount_skills(app, _skills)
scores = ReliabilityStore()
mount_console(app, registry, scores=scores)

# ---------------------------------------------------------------------------
# Product surfaces → filesystem-routed pages (Gaze / Resolve / Stars / …)
# ---------------------------------------------------------------------------

app.mount_pages(str(PAGES_DIR))


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
        return JSONResponse.from_value(
            {"error": "not_found", "name": name}, status=404
        )
    return JSONResponse.from_value(record.as_dict())


@app.route("/api/gaze/match", referenced=True)
def api_gaze_match(request: Request) -> JSONResponse:
    """Gaze match: ``?intent=`` (+ optional ``?node=``) → ranked hits JSON."""
    intent = (request.query.get("intent") or request.query.get("q") or "").strip()
    node = (request.query.get("node") or "public").strip() or "public"
    if node == "docs":
        hits = CATALOG.hits_for_node("docs")
    else:
        hits = CATALOG.match(intent, node=node) if intent else CATALOG.hits_for_node(node)
    return JSONResponse.from_value(
        {
            "intent": intent,
            "node": node,
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
        }
    )


# Publish-oracle dogfood: freeze + smoke after all routes are registered so the
# console shows ReliabilityScore values. Skip with ORRERY_SKIP_PUBLISH=1.
# Also skip ``run_smoke`` when an event loop is already running (async pytest
# loaders) — ``asyncio.run`` inside ``run_smoke`` cannot nest.
if os.environ.get("ORRERY_SKIP_PUBLISH", "").strip() not in ("1", "true", "True"):
    app.freeze()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        _smoke = run_smoke(app, DOGFOOD_CORPUS, answer_fn=render_faithful_answer)
        for _skill in registry.skills():
            scores.record(_skill.name, _smoke)


if __name__ == "__main__":
    app.run()
