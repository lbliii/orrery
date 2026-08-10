"""Public discovery documents for agents probing Orrery.

Discovery is intentional and open: llms.txt, MCP well-knowns, and /connect
point at the aggregated dogfood host. No bearer mint — CSRF-exempt /mcp is
the machine face. Skill DNS (mcp://) stays on ORRERY_MCP_HOST.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse

# Align with streamable-HTTP MCP clients common in 2025-2026.
MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_VERSION = "0.1.0"
TRUST_FACTS = (
    "Public Star and constellation results are signed Ed25519 Envelopes; public keys are at "
    "/.well-known/orrery/keys.json.",
    "Durable artifact downloads are authorized by stored metadata and expire after 15 minutes.",
    "Public Stars expose bounded declared tools; Orrery does not provide arbitrary shell or "
    "filesystem execution.",
)

# Static catalog for pre-connection probes (must stay in sync with aggregate /mcp).
MCP_TOOLS: tuple[dict[str, str], ...] = (
    {
        "name": "gaze_match",
        "description": (
            "Bounded shortlist for an intent (≤20 default; agent ranks). "
            "Facets + oracle pills; no tool payloads."
        ),
    },
    {
        "name": "gaze_search",
        "description": (
            "Search the public sky / namespace by query (bounded shortlist). "
            "Agent is the semantic router."
        ),
    },
    {
        "name": "gaze_describe",
        "description": "Describe a skill or constellation for an agent.",
    },
    {
        "name": "gaze_list_constellations",
        "description": "List drawn policy graphs (constellations).",
    },
    {
        "name": "coverage_check",
        "description": (
            "Preflight allowlist membership for a public star "
            "(repo/package/target/…). Returns {allowed, reason}."
        ),
    },
    {
        "name": "resolve_name",
        "description": "Resolve a Skill DNS name to endpoint, digest, key, price.",
    },
    {
        "name": "convert",
        "description": "Convert HTML to PDF (html-to-pdf star; aggregate alias).",
    },
    {
        "name": "health",
        "description": "Health check for the html-to-pdf star.",
    },
    {
        "name": "fetch",
        "description": "Fetch a live UTC reading (world-time star).",
    },
    {
        "name": "get",
        "description": "Get the last sealed world-time reading.",
    },
    {
        "name": "answer",
        "description": "Answer with a sealed live UTC reading (world-time).",
    },
    {
        "name": "observe",
        "description": "Observe an allowlisted official source (source-watch).",
    },
    {
        "name": "diff",
        "description": "Diff a prior source-watch observation against live content.",
    },
    {
        "name": "source_watch_answer",
        "description": "Extractive answer from source-watch (aggregate name).",
    },
    {
        "name": "run",
        "description": "Run a constellation policy graph.",
    },
    {
        "name": "status",
        "description": "Status for a constellation run.",
    },
    {
        "name": "explain_policy",
        "description": "Explain a constellation policy for an agent.",
    },
)

DIRECT_STAR_ENDPOINTS: tuple[dict[str, str], ...] = (
    {
        "path": "/stars/html-to-pdf/mcp",
        "star": "orrery/html-to-pdf",
        "tools": "convert, health",
    },
    {
        "path": "/stars/world-time/mcp",
        "star": "orrery/world-time",
        "tools": "fetch, get, answer",
    },
    {
        "path": "/stars/source-watch/mcp",
        "star": "orrery/source-watch",
        "tools": "observe, diff, answer",
    },
)

#: Cohort A teaching trio — point-don't-clone parable (#87 / epic #78).
TEACHING_TRIO: tuple[dict[str, str], ...] = (
    {
        "star": "orrery/world-time",
        "job": "Live truth — seal a fresh UTC instant at call time",
        "href": "/stars?name=orrery/world-time",
    },
    {
        "star": "orrery/source-watch",
        "job": "Observe/diff — re-check an allowlisted official source",
        "href": "/stars?name=orrery/source-watch",
    },
    {
        "star": "orrery/html-to-pdf",
        "job": "Faucet + Envelope — tangible convert with a signed receipt",
        "href": "/stars?name=orrery/html-to-pdf",
    },
)

#: Plain-language capability family blurbs for llms-full grouping (#225).
CAPABILITY_FAMILY_DESCRIPTIONS: dict[str, str] = {
    "time_and_date": (
        "Seal live clock evidence at call time — offline clones go stale by definition."
    ),
    "source_monitoring": (
        "Observe allowlisted official sources, digests, release notes, and normative sections."
    ),
    "document_processing": (
        "Render trusted documents into short-lived artifacts with signed receipts."
    ),
    "data": ("Bounded CSV samples, lookups, validation, diffs, and table freshness verdicts."),
    "web_metadata": ("Fresh HTTP headers and slices of allowlisted discovery documents."),
    "security": ("TLS expiry, SPDX license text, and ship-check evidence bundles."),
    "media": ("Bounded image transforms on Orrery's managed CPU worker."),
}

#: Common intents → recommended public SKUs only (no invented catalog names).
PUBLIC_CATALOG_RECIPES: tuple[tuple[str, str], ...] = (
    ("fresh timestamp for citation", "orrery/world-time"),
    ("stale answer detection", "orrery/stale-proof"),
    ("html → pdf with receipt", "orrery/html-to-pdf"),
    ("observe allowlisted official source", "orrery/source-watch"),
    ("ship-check evidence before reasoning", "orrery/ship-check"),
    ("table freshness verdict", "orrery/table-fresh"),
    ("pinned github file at commit", "orrery/gh-file-at-ref"),
    ("tls certificate expiry", "orrery/cert-expiry"),
)

#: Stable family section order (teaching-adjacent first, then alpha by key).
_FAMILY_SECTION_ORDER: tuple[str, ...] = (
    "time_and_date",
    "source_monitoring",
    "document_processing",
    "data",
    "web_metadata",
    "security",
    "media",
)

DISCOVERY_CACHE_CONTROL = "public, max-age=3600"
DISCOVERY_CORS = "*"
GITHUB_REPO = "https://github.com/lbliii/orrery"
SECURITY_CONTACT = f"{GITHUB_REPO}/security/advisories/new"
SUPPORT_CONTACT = f"{GITHUB_REPO}/issues/new/choose"


def configured_public_origin() -> str | None:
    """Resolve ORRERY_PUBLIC_ORIGIN, then Railway public domain."""
    origin = (os.environ.get("ORRERY_PUBLIC_ORIGIN") or "").strip().rstrip("/")
    if origin:
        return origin
    railway_domain = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip()
    if railway_domain:
        return f"https://{railway_domain}"
    return None


def resolve_public_origin(public_origin: str | None, request_url: str | Any) -> str:
    """Canonical HTTPS (or local) origin for discovery URLs."""
    if public_origin:
        return public_origin.rstrip("/")
    if isinstance(request_url, str):
        parsed = urlparse(request_url)
        scheme = parsed.scheme or "http"
        netloc = parsed.netloc or "127.0.0.1:8000"
        return f"{scheme}://{netloc}"
    scheme = getattr(request_url, "scheme", None) or "http"
    netloc = getattr(request_url, "netloc", None) or "127.0.0.1:8000"
    return f"{scheme}://{netloc}"


def mcp_endpoint(origin: str) -> str:
    return f"{origin.rstrip('/')}/mcp"


def server_card(origin: str) -> dict[str, Any]:
    """SEP-1649-shaped MCP server card (draft; pre-connection catalog)."""
    endpoint = mcp_endpoint(origin)
    return {
        "$schema": "https://modelcontextprotocol.io/schemas/server-card.json",
        "version": "1.0",
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "serverInfo": {
            "name": "orrery",
            "title": "Orrery — Skill DNS MCP",
            "version": SERVER_VERSION,
        },
        "description": (
            "Skills you point at, not install. Gaze to discover, resolve to lock "
            "endpoint/digest/key/price, call publisher MCP, seal with a Chirp "
            "Envelope. Aggregated dogfood host at /mcp; direct stars at "
            "/stars/*/mcp. Authentication not required on the public host."
        ),
        "homepage": f"{origin}/connect",
        "documentation": f"{origin}/llms.txt",
        "llms_full": f"{origin}/llms-full.txt",
        "envelope_keys": f"{origin}/.well-known/orrery/keys.json",
        "transport": {
            "type": "streamable-http",
            "endpoint": endpoint,
        },
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
            "prompts": {"listChanged": False},
        },
        "authentication": {
            "required": False,
            "schemes": [],
            "instructions": (
                "Point a streamable-HTTP MCP client at /mcp with no auth headers. "
                "Prefer resolve_name then call the publisher direct endpoint from "
                "the Skill DNS record when locking a star."
            ),
        },
        "tools": [{"name": t["name"], "description": t["description"]} for t in MCP_TOOLS],
    }


def mcp_manifest(origin: str) -> dict[str, Any]:
    """SEP-1960-shaped MCP discovery manifest (draft; connect focus)."""
    endpoint = mcp_endpoint(origin)
    return {
        "mcp_version": "1.0",
        "server_version": SERVER_VERSION,
        "endpoints": {
            "streamable_http": endpoint,
        },
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False,
            "sampling": False,
            "roots": False,
        },
        "authentication": {
            "required": False,
            "methods": [],
            "connect_url": f"{origin}/connect",
        },
        "security": {
            "tls_required": origin.startswith("https://"),
            "security_contact": SECURITY_CONTACT,
        },
        "registration": {"dynamic": False},
        "documentation": f"{origin}/llms.txt",
        "llms_full": f"{origin}/llms-full.txt",
        "homepage": f"{origin}/connect",
        "envelope_keys": f"{origin}/.well-known/orrery/keys.json",
    }


def llms_txt(origin: str) -> str:
    """Compact llms.txt for crawlers and agents (llmstxt.org-style)."""
    endpoint = mcp_endpoint(origin)
    trio_lines = [f"- [`{t['star']}`]({origin}{t['href']}): {t['job']}" for t in TEACHING_TRIO]
    lines = [
        "# Orrery",
        "",
        "> Skills you point at, not install.",
        "> Gaze to discover, resolve to lock the record, call for a verified result.",
        "> Public discovery and aggregated MCP — no bearer mint on the dogfood host.",
        "> Do not install or clone for live truth — point at the teaching trio below.",
        "",
        "## Connect",
        "",
        f"- [Connect guide]({origin}/connect): point an MCP client at Orrery",
        f"- [MCP endpoint]({endpoint}): streamable HTTP; no Authorization header",
        f"- [Skill discovery]({origin}/skills): Chirp JSON skill list",
        f"- [Health]({origin}/health): liveness probe",
        f"- [Envelope verification keys]({origin}/.well-known/orrery/keys.json): "
        "Ed25519 public keys",
        "",
        "## Teaching trio (cohort A)",
        "",
        "Point — don't clone. Offline copies cannot mint fresh UTC or re-observe upstream.",
        "",
        *trio_lines,
        f"- [`orrery/stale-proof`]({origin}/constellations?name=orrery/stale-proof): "
        "composite that seals now + observe/diff (+ optional PDF receipt)",
        "",
        "## Discovery",
        "",
        f"- [llms.txt]({origin}/llms.txt): this file",
        f"- [llms-full.txt]({origin}/llms-full.txt): full public catalog from Agent Cards",
        f"- [MCP server card]({origin}/.well-known/mcp/server-card.json): SEP-1649-shaped catalog",
        f"- [MCP manifest]({origin}/.well-known/mcp): SEP-1960-shaped connect",
        "",
        "## Product",
        "",
        f"- [Gaze]({origin}/gaze): discover / match intent",
        f"- [Resolve]({origin}/resolve): Skill DNS lock (endpoint, digest, key, price)",
        f"- [Stars]({origin}/stars): callable hosted skills",
        "- Skill DNS: `mcp://orrery.lol/…` (override host with `ORRERY_MCP_HOST`)",
        "",
        "## Optional",
        "",
        f"- [Source]({GITHUB_REPO})",
        f"- [Home]({origin}/)",
        "",
    ]
    return "\n".join(lines)


def resolve_href(origin: str, name: str) -> str:
    """Machine-facing resolve URL for a Skill DNS name."""
    return f"{origin.rstrip('/')}/api/resolve?name={name}"


def public_star_catalog() -> tuple[dict[str, Any], ...]:
    """Public star entries projected from manifests + Agent Cards (#225).

    Returns one dict per builtin public star with ``name``, ``families``,
    ``family_labels``, ``summary``, ``use_when``, ``example_intents``.
    """
    from catalog.agent_card import require_card
    from stars._core.definition import CAPABILITY_FAMILY_LABELS
    from stars._core.registry import load_builtin_star_definition
    from stars.builtins import BUILTIN_STAR_PACKAGES

    entries: list[dict[str, Any]] = []
    for package in BUILTIN_STAR_PACKAGES:
        definition = load_builtin_star_definition(package)
        card = require_card(definition.name)
        families = tuple(definition.capability_families)
        entries.append(
            {
                "name": definition.name,
                "families": families,
                "primary_family": families[0] if families else "source_monitoring",
                "family_labels": tuple(
                    CAPABILITY_FAMILY_LABELS.get(family, family.replace("_", " ").title())
                    for family in families
                ),
                "summary": card.summary,
                "use_when": tuple(card.use_when),
                "example_intents": tuple(card.example_intents),
            }
        )
    return tuple(sorted(entries, key=lambda item: str(item["name"])))


def _family_section_keys(entries: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    present = {str(item["primary_family"]) for item in entries}
    ordered = [key for key in _FAMILY_SECTION_ORDER if key in present]
    extras = sorted(present - set(_FAMILY_SECTION_ORDER))
    return tuple(ordered + extras)


def public_catalog_section(origin: str) -> str:
    """Markdown section: full public sky grouped by capability family."""
    from stars._core.definition import CAPABILITY_FAMILY_LABELS

    entries = public_star_catalog()
    lines: list[str] = [
        "## Public catalog",
        "",
        "Indexed from Agent Cards (summary / use_when / example_intents). "
        "Groupings follow each star's primary capability family.",
        "",
    ]
    for family in _family_section_keys(entries):
        label = CAPABILITY_FAMILY_LABELS.get(family, family.replace("_", " ").title())
        description = CAPABILITY_FAMILY_DESCRIPTIONS.get(
            family,
            "Public skills in this capability family.",
        )
        lines.extend([f"### {label}", "", description, ""])
        family_entries = [item for item in entries if item["primary_family"] == family]
        for item in family_entries:
            name = str(item["name"])
            lines.extend(
                [
                    f"#### `{name}`",
                    "",
                    f"- Summary: {item['summary']}",
                    "- Use when:",
                    *[f"  - {bullet}" for bullet in item["use_when"]],
                    "- Example intents: "
                    + ", ".join(f"`{intent}`" for intent in item["example_intents"]),
                    f"- Resolve: {resolve_href(origin, name)}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def recipes_section() -> str:
    """Markdown recipes table — common intents to existing public SKUs."""
    public_names = {str(item["name"]) for item in public_star_catalog()}
    unknown = sorted({sku for _, sku in PUBLIC_CATALOG_RECIPES if sku not in public_names})
    if unknown:
        raise ValueError(f"PUBLIC_CATALOG_RECIPES references unknown public SKUs: {unknown}")
    lines = [
        "## Recipes",
        "",
        "Common intent → try first (public sky SKUs only):",
        "",
        "| Intent | Try first |",
        "|--------|-----------|",
        *[f"| {intent} | `{sku}` |" for intent, sku in PUBLIC_CATALOG_RECIPES],
        "",
    ]
    return "\n".join(lines)


def llms_full_txt(origin: str) -> str:
    """Expanded agent onboarding text — teaching trio, then full public catalog."""
    endpoint = mcp_endpoint(origin)
    tool_lines = [f"- `{t['name']}`: {t['description']}" for t in MCP_TOOLS]
    star_lines = [
        f"- `{s['star']}` → `{origin}{s['path']}` ({s['tools']})" for s in DIRECT_STAR_ENDPOINTS
    ]
    body = [
        llms_txt(origin).rstrip(),
        "",
        public_catalog_section(origin).rstrip(),
        "",
        recipes_section().rstrip(),
        "",
        "## MCP tools (aggregate /mcp)",
        "",
        *tool_lines,
        "",
        "## Direct star endpoints",
        "",
        "Resolve records prefer these; canonical tool names without aggregate collisions:",
        "",
        *star_lines,
        "",
        "## Cursor snippet",
        "",
        "Paste:",
        "",
        "```json",
        "{",
        '  "mcpServers": {',
        '    "orrery": {',
        f'      "url": "{endpoint}"',
        "    }",
        "  }",
        "}",
        "```",
        "",
        "## Smoke test",
        "",
        "```bash",
        f'BASE="{origin}"',
        "",
        'curl -sS "$BASE/mcp" \\',
        "  -H 'Content-Type: application/json' \\",
        "  -H 'mcp-protocol-version: 2025-06-18' \\",
        '  -d \'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\'',
        "",
        'curl -sS "$BASE/mcp" \\',
        "  -H 'Content-Type: application/json' \\",
        "  -H 'mcp-protocol-version: 2025-06-18' \\",
        '  -d \'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{',
        '        "name":"gaze_match",',
        '        "arguments":{"intent":"html pdf convert","node":"public"}',
        "      }}'",
        "```",
        "",
        "## Do not",
        "",
        "- Treat Orrery as a proxy — Call goes agent → publisher MCP (ADR 0004)",
        "- Expect a bearer mint on the public dogfood host",
        "- Install or clone for live truth — resolve `orrery/world-time` / "
        "`orrery/source-watch` and call; offline clones go stale by definition",
        "",
    ]
    return "\n".join(body)


def robots_txt(origin: str) -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Allow: /connect",
            "Allow: /llms.txt",
            "Allow: /llms-full.txt",
            "Allow: /.well-known/",
            "Allow: /gaze",
            "Allow: /resolve",
            "Allow: /stars",
            "Allow: /constellations",
            "Allow: /namespaces",
            "Allow: /skills",
            "Allow: /mcp",
            "Allow: /health",
            "Allow: /ready",
            "Allow: /static/",
            "Disallow: /console",
            f"Sitemap: {origin}/sitemap.xml",
            "",
        ]
    )


def security_txt(origin: str) -> str:
    return "\n".join(
        [
            f"Contact: {SECURITY_CONTACT}",
            f"Canonical: {origin}/.well-known/security.txt",
            "Preferred-Languages: en",
            f"Policy: {origin}/security",
            "Expires: 2027-01-01T00:00:00.000Z",
            "",
        ]
    )


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"
