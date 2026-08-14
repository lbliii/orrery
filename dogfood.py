"""Temporary dogfood skills for the Orrery host — N wrapped ``chirp.skill`` apps.

Gaze / Resolve / html-to-pdf / world-time / source-watch share one aggregated ``/mcp`` with
unique tool names. Gaze discovers skills (``gaze_match`` / ``gaze_search`` /
``gaze_describe`` / ``gaze_list_constellations`` / ``coverage_check``); Resolve returns Skill DNS
via ``resolve_name``; html-to-pdf is the Call / Envelope plumbing demo (issues
#25-#27); world-time is the Wave 1 reactive expertise spike (#37) — live UTC
payload sealed at call time. Source Watch observes an allowlisted official
source and seals current evidence or a bounded answer at call time (#51).

Each skill has a golden corpus entry that passes the publish oracle
(``run_publish_gate`` / smoke harness). Public star packages also ship their
own non-empty ``corpus.py`` ``CORPUS`` (L1 / #117); missing corpus ⇒ not
``oracle_ok``.
"""

from __future__ import annotations

import os
from typing import Any

from chirp.http.request import Request
from chirp.http.response import Response
from chirp.skill import Envelope, Skill, verify_envelope
from chirp.skill.mount import use_skill
from chirp.skill.registry import SkillRegistry
from chirp.skill.smoke import CorpusPrompt
from chirp.tools.handler import handle_mcp_request
from chirp.tools.live_log import DEFAULT_INVOCATION_LOG_PATH, mount_invocation_log
from chirp.tools.registry import ToolDef, ToolRegistry
from chirp.tools.schema import function_to_schema
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog import CATALOG, GAZE_DEFAULT_LIMIT, GAZE_MAX_LIMIT
from catalog.call_skill_proxy import forward_call_skill
from catalog.constellation_run import explain_policy, run_constellation, status_for_run
from catalog.coverage import check_coverage, describe_coverage
from catalog.mcp_tool_content import wrap_structured_mcp_handler
from discovery import MCP_TOOLS_ALLOWLIST
from listings.mcp import build_listing_skill
from public_keys import key_set_url
from stars.decision_bind.service import bind as bind_decision
from stars.html_to_pdf.skill import build_skill as build_html_to_pdf_star
from stars.source_watch.skill import build_skill as build_source_watch_star
from stars.world_time.service import fetch_live_utc as _fetch_live_utc
from stars.world_time.skill import build_skill as build_world_time_star
from trust.satisfaction import build_satisfaction_skill

#: How many dogfood skills this host mounts (Foundation epic #2 + Waves 1/2 + satisfaction).
N_DOGFOOD_SKILLS = 7

#: Labeled aggregate for teaching-trio / constellation **call** demos (not in /connect).
DOGFOOD_MCP_PATH = "/mcp/dogfood"

#: Smoke HTML used by the star detail receipt and corpus.
SMOKE_HTML = "<!doctype html><html><body><h1>Orrery</h1></body></html>"

_html_to_pdf_skill: Skill | None = None
_world_time_skill: Skill | None = None
_source_watch_skill: Skill | None = None
_gaze_skill: Skill | None = None
_resolve_skill: Skill | None = None
_launch_gate_skill: Skill | None = None
_discovery_launch_gate_skill: Skill | None = None
_listing_skill: Skill | None = None

def _load_or_generate_key(env_name: str) -> Ed25519PrivateKey:
    raw = os.environ.get(env_name, "").strip()
    if raw:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
    return Ed25519PrivateKey.generate()


def fetch_live_utc() -> dict[str, object]:
    """Compatibility import for the World Time Star's package service."""
    return _fetch_live_utc()


def use_skill_structured_mcp(app: Any, skill: Skill) -> Skill:
    """Mount ``skill`` tools returning ADR 0010 JSON on MCP ``tools/call``."""
    for pending in skill._pending:
        pending.handler = wrap_structured_mcp_handler(
            pending.handler,
            skill=skill.name,
            tool=pending.name,
        )
    return use_skill(app, skill)


def get_gaze_skill() -> Skill:
    """Return the shared gaze skill (same instance on ``/mcp`` and registry)."""
    global _gaze_skill
    if _gaze_skill is None:
        _gaze_skill = build_gaze_skill()
    return _gaze_skill


def get_resolve_skill() -> Skill:
    """Return the shared resolve skill (same instance on ``/mcp`` and registry)."""
    global _resolve_skill
    if _resolve_skill is None:
        _resolve_skill = build_resolve_skill()
    return _resolve_skill


def get_launch_gate_skill() -> Skill:
    """Return the full launch-gate skill (``/mcp/dogfood`` run/status)."""
    global _launch_gate_skill
    if _launch_gate_skill is None:
        _launch_gate_skill = build_launch_gate_skill()
    return _launch_gate_skill


def get_discovery_launch_gate_skill() -> Skill:
    """Return slim launch-gate (``explain_policy`` on aggregate ``/mcp``)."""
    global _discovery_launch_gate_skill
    if _discovery_launch_gate_skill is None:
        _discovery_launch_gate_skill = build_launch_gate_skill(discovery_only=True)
    return _discovery_launch_gate_skill


def get_listing_skill() -> Skill:
    """Return opt-in listing skill (``index_ping`` / ``rate_listing`` on ``/mcp``)."""
    global _listing_skill
    if _listing_skill is None:
        _listing_skill = build_listing_skill(verify_receipt=verify_receipt)
    return _listing_skill


def build_gaze_skill(*, private_key: Any | None = None) -> Skill:
    """Gaze — progressive-disclosure discovery over the skill catalog."""
    private = private_key or _load_or_generate_key("ORRERY_GAZE_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "gaze",
        version="1.0.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_GAZE_KEY_ID", "gaze-1"),
        public_key=public,
    )

    @skill.tool(
        "gaze_match",
        description=(
            "Match an intent to a bounded shortlist of catalog hits "
            "(name, blurb, endpoint, price, facets, oracle). "
            "Agent ranks the shortlist — Orrery does not pick a winner. "
            f"Default limit {GAZE_DEFAULT_LIMIT}; explicit limit capped at {GAZE_MAX_LIMIT}."
        ),
    )
    def gaze_match(
        intent: str,
        node: str = "public",
        limit: int = GAZE_DEFAULT_LIMIT,
    ) -> dict[str, object]:
        hits = CATALOG.match(intent, node=node or "public", limit=limit)
        return {
            "intent": intent,
            "node": node or "public",
            "limit": len(hits),
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
            "note": "Agent is the semantic router; re-rank or filter by facets.",
        }

    @skill.tool(
        "gaze_search",
        description=(
            "Search catalog names, descriptions, and agent-card text "
            "(summary, use_when, example_intents) by substring "
            "(bounded shortlist with facets; no tool payloads). "
            f"Default limit {GAZE_DEFAULT_LIMIT}; explicit limit capped at {GAZE_MAX_LIMIT}."
        ),
    )
    def gaze_search(
        query: str,
        node: str = "public",
        limit: int = GAZE_DEFAULT_LIMIT,
    ) -> dict[str, object]:
        scoped = node or "public"
        hits = CATALOG.search(query, node=scoped, limit=limit)
        return {
            "query": query,
            "node": scoped,
            "limit": len(hits),
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
            "note": "Agent is the semantic router; re-rank or filter by facets.",
        }

    @skill.tool(
        "gaze_describe",
        description="Describe a skill by name (manifest + full agent card, no execution)",
    )
    def gaze_describe(name: str) -> dict[str, object]:
        return CATALOG.describe(name)

    @skill.tool(
        "gaze_list_constellations",
        description="List constellation-kind records in the catalog",
    )
    def gaze_list_constellations(node: str = "public") -> dict[str, object]:
        scoped = node or "public"
        hits = CATALOG.list_constellations(node=scoped)
        return {
            "node": scoped,
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
        }

    @skill.tool(
        "coverage_check",
        description=(
            "Preflight an allowlist-gated star: pass star (or short id) plus the "
            "same param names as that star's MCP tools (target, package, host, …). "
            "Returns {allowed, reason}; on deny, includes allowed_values sample "
            "and/or catalog_href."
        ),
    )
    def coverage_check_tool(
        star: str,
        repo: str = "",
        package: str = "",
        target: str = "",
        host: str = "",
        document: str = "",
        dataset: str = "",
        source: str = "",
        pep: str = "",
        rfc: str = "",
        section: str = "",
        license_id: str = "",
        profile: str = "",
    ) -> dict[str, object]:
        params = {
            key: value
            for key, value in {
                "repo": repo,
                "package": package,
                "target": target,
                "host": host,
                "document": document,
                "dataset": dataset,
                "source": source,
                "pep": pep,
                "rfc": rfc,
                "section": section,
                "license_id": license_id,
                "profile": profile,
            }.items()
            if value
        }
        # Prefer membership check when any param is set; otherwise describe.
        if params:
            return check_coverage(star, params=params)
        described = describe_coverage(star)
        if described is None:
            return {"allowed": False, "reason": "unknown_star", "star": star}
        return described

    return skill


def build_resolve_skill(*, private_key: Any | None = None) -> Skill:
    """Resolve — Skill DNS: name → endpoint, digest, key, price."""
    private = private_key or _load_or_generate_key("ORRERY_RESOLVE_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "resolve",
        version="1.0.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_RESOLVE_KEY_ID", "resolve-1"),
        public_key=public,
    )

    @skill.tool(
        "resolve_name",
        description="Resolve a skill name to a Skill DNS record (endpoint, digest, key, price)",
    )
    def resolve_name(name: str) -> dict[str, object]:
        from catalog.example_arguments import example_arguments_for_tools

        record = CATALOG.resolve(name)
        if record is None:
            return {"error": "not_found", "name": name, "status": "not_found"}
        payload = record.as_dict()
        payload["example_arguments"] = example_arguments_for_tools(name, record.tools)
        # The aggregate MCP tool has no request object; deployments should set
        # ORRERY_PUBLIC_ORIGIN. The public host is the safe discovery fallback.
        payload["public_key_url"] = key_set_url(
            os.environ.get("ORRERY_PUBLIC_ORIGIN", "https://orrery.lol")
        )
        payload["status"] = "resolved"
        return payload

    return skill


def _register_call_skill_tool(app: Any) -> None:
    """Mount unsigned ``call_skill`` on aggregate ``/mcp`` (returns JSON, not Envelope)."""

    @app.tool(
        "call_skill",
        description=(
            "Execute one publisher tool for a Skill DNS name via same-origin forward. "
            "Inputs: name (Skill DNS), tool (publisher tool), arguments (object, default {}). "
            "Returns JSON status/payload/envelope_wire; off-origin names require publisher-direct."
        ),
    )
    async def call_skill(
        name: str,
        tool: str,
        arguments: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return await forward_call_skill(app, name=name, tool=tool, arguments=arguments)


def build_html_to_pdf_skill(*, private_key: Any | None = None) -> Skill:
    """Build the aggregate adapter for the html-to-pdf Star package."""
    return build_html_to_pdf_star(private_key=private_key)


def build_world_time_skill(*, private_key: Any | None = None) -> Skill:
    """Build the aggregate adapter for the World Time Star package."""
    return build_world_time_star(private_key=private_key)


def build_source_watch_skill(*, private_key: Any | None = None) -> Skill:
    """Build the prefixed Source Watch adapter for the aggregate MCP host."""
    return build_source_watch_star(
        private_key=private_key,
        answer_tool_name="source_watch_answer",
    )


def build_launch_gate_skill(
    *,
    private_key: Any | None = None,
    discovery_only: bool = False,
) -> Skill:
    """launch-gate — constellation orchestration (run / status / explain_policy, #33)."""
    private = private_key or _load_or_generate_key("ORRERY_LAUNCH_GATE_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "launch-gate",
        version="2.0.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_LAUNCH_GATE_KEY_ID", "acme-launch-gate-1"),
        public_key=public,
    )

    if not discovery_only:

        @skill.tool(
            "run",
            description=(
                "Execute a constellation policy graph on a Doc Bundle input shape: "
                "pages (string[]), links (string[]), examples (string[]). "
                "Optional constellation name (default acme/launch-gate). "
                "Returns a signed composite Envelope chain "
                "(dispositions: ready | not-ready | stale | blocked)."
            ),
        )
        def run(
            pages: list[str] | None = None,
            links: list[str] | None = None,
            examples: list[str] | None = None,
            constellation: str = "acme/launch-gate",
            decision_id: str = "",
            decision_statement: str = "",
        ) -> dict[str, object]:
            bundle = {
                "pages": list(pages or []),
                "links": list(links or []),
                "examples": list(examples or []),
            }
            cites: list[str] | None = None
            if decision_id.strip() or decision_statement.strip():
                if not decision_id.strip() or not decision_statement.strip():
                    return {
                        "error": "decision_incomplete",
                        "status": "invalid",
                        "note": "Provide both decision_id and decision_statement to cite a freeze.",
                    }
                bound = bind_decision(decision_id.strip(), decision_statement)
                if "error" in bound:
                    return {"status": "invalid", **bound}
                cites = [str(bound["decision_digest"])]
            return run_constellation(
                bundle,
                constellation=constellation,
                skill_name=skill.name,
                skill_version=skill.version,
                key_id=skill.key_id,
                private_key=private,
                cites=cites,
            )

        @skill.tool(
            "status",
            description="Composite receipt / in-flight chain for a constellation run",
        )
        def status(run_id: str = "") -> dict[str, object]:
            return status_for_run(run_id)

    @skill.tool(
        "explain_policy",
        description=(
            "Explain a constellation: graph_summary, input schema, "
            "disposition enum, run_contract, gates/loops/fan-in "
            "(aligned with Agent Card fields; sealed Envelope)"
        ),
    )
    def explain_policy_tool(name: str = "acme/launch-gate") -> dict[str, object]:
        return explain_policy(name)

    return skill


def get_html_to_pdf_skill() -> Skill:
    """Return the shared html-to-pdf skill (same instance the host mounts)."""
    global _html_to_pdf_skill
    if _html_to_pdf_skill is None:
        _html_to_pdf_skill = build_html_to_pdf_skill()
    return _html_to_pdf_skill


def get_world_time_skill() -> Skill:
    """Return the shared world-time skill (same instance the host mounts)."""
    global _world_time_skill
    if _world_time_skill is None:
        _world_time_skill = build_world_time_skill()
    return _world_time_skill


def get_source_watch_skill() -> Skill:
    """Return the shared Source Watch skill without mounting it implicitly."""
    global _source_watch_skill
    if _source_watch_skill is None:
        _source_watch_skill = build_source_watch_skill()
    return _source_watch_skill


def _tool_handler(skill: Skill, name: str) -> Any:
    for pending in skill._pending:
        if pending.name == name:
            return pending.handler
    msg = f"Skill {skill.name!r} has no tool {name!r}"
    raise KeyError(msg)


def _price_for_skill(skill_name: str) -> str | None:
    """Look up ``price_per_call`` from the resolve catalog (demo star pricing)."""
    # Chirp wire ``skill`` is bare (``html-to-pdf``); catalog uses ``orrery/…``.
    record = CATALOG.resolve(skill_name) or CATALOG.resolve(f"orrery/{skill_name}")
    return record.price_per_call if record is not None else None


def signed_convert_receipt(
    html: str = SMOKE_HTML,
    *,
    skill: Skill | None = None,
) -> tuple[dict[str, Any], bool]:
    """Invoke ``convert`` and return ``(receipt_dict, verified)``.

    Receipt includes Chirp Envelope wire fields plus ``payment_id`` and
    ``price_per_call`` for commerce stub hooks (#35).
    """
    sk = skill or get_html_to_pdf_skill()
    envelope: Envelope = _tool_handler(sk, "convert")(html=html)
    verified = verify_envelope(envelope, sk.public_key)
    receipt = envelope.to_wire()
    receipt["payment_id"] = f"pay_{envelope.nonce[:12]}"
    receipt["price_per_call"] = _price_for_skill(str(receipt.get("skill", sk.name)))
    return receipt, verified


def signed_world_time_receipt(
    *,
    tool: str = "answer",
    skill: Skill | None = None,
) -> tuple[dict[str, Any], bool]:
    """Invoke a world-time tool and return ``(receipt_dict, verified)``."""
    sk = skill or get_world_time_skill()
    envelope: Envelope = _tool_handler(sk, tool)()
    verified = verify_envelope(envelope, sk.public_key)
    receipt = envelope.to_wire()
    receipt["payment_id"] = "pay_world_time"
    receipt["price_per_call"] = _price_for_skill(str(receipt.get("skill", sk.name)))
    return receipt, verified


def signed_source_watch_receipt(
    *,
    source: str = "python-release-notes",
    skill: Skill | None = None,
) -> tuple[dict[str, Any], bool]:
    """Observe an allowlisted source and return its signed receipt."""
    sk = skill or get_source_watch_skill()
    envelope: Envelope = _tool_handler(sk, "observe")(source=source)
    verified = verify_envelope(envelope, sk.public_key)
    receipt = envelope.to_wire()
    receipt["payment_id"] = "pay_source_watch"
    receipt["price_per_call"] = _price_for_skill(str(receipt.get("skill", sk.name)))
    return receipt, verified


def envelope_from_wire(data: dict[str, Any]) -> Envelope:
    """Rebuild an :class:`Envelope` from a wire / receipt dict (fails closed)."""
    return Envelope(
        payload=data["payload"],
        skill=str(data["skill"]),
        version=str(data["version"]),
        tool=str(data["tool"]),
        nonce=str(data["nonce"]),
        input_digest=str(data["input_digest"]),
        signature=str(data["signature"]),
        key_id=str(data["key_id"]),
        alg=str(data.get("alg", "Ed25519")),
    )


def skill_for_receipt(data: dict[str, Any]) -> Skill | None:
    """Pick the dogfood skill whose public key should verify this receipt."""
    name = str(data.get("skill") or "")
    tool = str(data.get("tool") or "")
    if name == "gaze":
        return get_gaze_skill()
    if name == "resolve":
        return get_resolve_skill()
    if name == "launch-gate":
        if tool == "explain_policy":
            return get_discovery_launch_gate_skill()
        return get_launch_gate_skill()
    if name == "html-to-pdf":
        return get_html_to_pdf_skill()
    if name == "world-time":
        return get_world_time_skill()
    if name == "source-watch":
        return get_source_watch_skill()
    return None


def verify_receipt(
    data: dict[str, Any],
    *,
    skill: Skill | None = None,
) -> bool:
    """Verify a receipt dict against the matching dogfood public key."""
    sk = skill or skill_for_receipt(data)
    if sk is None:
        return False
    try:
        env = envelope_from_wire(data)
    except (KeyError, TypeError, ValueError):
        return False
    if sk.public_key is None:
        return False
    return verify_envelope(env, sk.public_key)


def build_discovery_skills() -> tuple[Skill, ...]:
    """Slim default ``/mcp`` — gaze, resolve, and constellation explain only."""
    return (
        get_gaze_skill(),
        get_resolve_skill(),
        get_discovery_launch_gate_skill(),
        get_listing_skill(),
    )


def build_dogfood_call_skills() -> tuple[Skill, ...]:
    """Teaching-trio / constellation call tools for ``/mcp/dogfood`` or direct mounts."""
    return (
        get_html_to_pdf_skill(),
        get_world_time_skill(),
        get_source_watch_skill(),
        get_launch_gate_skill(),
        build_satisfaction_skill(verify_receipt=verify_receipt),
    )


def build_dogfood_skills() -> tuple[Skill, ...]:
    """Return the N dogfood skills in mount order (console + publish-oracle registry)."""
    skills = (
        get_gaze_skill(),
        get_resolve_skill(),
        get_html_to_pdf_skill(),
        get_world_time_skill(),
        get_source_watch_skill(),
        get_launch_gate_skill(),
        build_satisfaction_skill(verify_receipt=verify_receipt),
    )
    assert len(skills) == N_DOGFOOD_SKILLS
    return skills


def _skills_tool_registry(app: Any, skills: tuple[Skill, ...]) -> ToolRegistry:
    """Compile skill pending tools into one isolated MCP registry."""
    seen: dict[str, str] = {}
    tools: list[ToolDef] = []
    for skill in skills:
        for pending in skill._pending:
            owner = seen.get(pending.name)
            if owner is not None:
                msg = (
                    f"Duplicate tool name {pending.name!r} across skills "
                    f"{owner!r} and {skill.name!r}; dogfood MCP requires unique names"
                )
                raise ValueError(msg)
            seen[pending.name] = skill.name
            tools.append(
                ToolDef(
                    name=pending.name,
                    description=pending.description,
                    handler=wrap_structured_mcp_handler(
                        pending.handler,
                        skill=skill.name,
                        tool=pending.name,
                    ),
                    schema=function_to_schema(pending.handler),
                    approval_required=pending.approval_required,
                )
            )
    return ToolRegistry(tools, app.tool_events)


def mount_dogfood_mcp(
    app: Any,
    skills: tuple[Skill, ...],
    *,
    path: str = DOGFOOD_MCP_PATH,
) -> ToolRegistry:
    """Mount call-tool aggregate at a labeled path (not advertised by ``/connect``)."""
    registry = _skills_tool_registry(app, skills)

    async def dogfood_mcp_handler(request: Request) -> Response:
        return await handle_mcp_request(request, registry)

    dogfood_mcp_handler.__name__ = "dogfood_mcp"
    app.route(path, methods=["POST"], referenced=True)(dogfood_mcp_handler)
    return registry


def _register_skill_discovery(app: Any, registry: SkillRegistry, path: str) -> None:
    @app.route(path, methods=["GET"], name="chirp_skill_discovery")
    def skill_discovery() -> dict[str, object]:
        return registry.discovery_document()


def mount_orrery_skills(
    app: Any,
    *,
    registry: SkillRegistry,
    discovery_skills: tuple[Skill, ...],
    call_skills: tuple[Skill, ...],
    discovery_path: str = "/skills",
    invocation_log_path: str | None = DEFAULT_INVOCATION_LOG_PATH,
) -> ToolRegistry:
    """Wire slim ``/mcp``, labeled ``/mcp/dogfood``, discovery, and live invocation log."""
    for skill in discovery_skills:
        use_skill_structured_mcp(app, skill)
    _register_call_skill_tool(app)
    _register_skill_discovery(app, registry, discovery_path)
    if invocation_log_path is not None:
        mount_invocation_log(app, path=invocation_log_path)
    return mount_dogfood_mcp(app, call_skills)


def run_dogfood_publish_gate(
    app: Any,
    corpus: tuple[CorpusPrompt, ...],
    *,
    dogfood_registry: ToolRegistry,
    answer_fn: Any | None = None,
    warnings_as_errors: bool = False,
) -> Any:
    """Publish gate with call tools routed through ``/mcp/dogfood`` registry."""
    from chirp.skill.publish import (
        STAGE_SMOKE,
        PublishReceipt,
        StageResult,
        _check_stage,
        _freeze_stage,
    )
    from chirp.skill.smoke import run_smoke

    check = _check_stage(app, warnings_as_errors=warnings_as_errors)
    freeze, manifests = _freeze_stage(app)

    async def _call_tool(tool: str, arguments: dict[str, object]) -> Any:
        if tool in MCP_TOOLS_ALLOWLIST:
            return await app.tools.call_tool(tool, arguments)
        return await dogfood_registry.call_tool(tool, arguments)

    try:
        report = run_smoke(app, corpus, answer_fn=answer_fn, call_tool=_call_tool)
    except Exception as exc:
        smoke = StageResult(
            name=STAGE_SMOKE,
            passed=False,
            summary=f"smoke raised {type(exc).__name__}: {exc}",
            detail={"error": str(exc)},
        )
        return PublishReceipt(
            passed=False,
            stages=(check, freeze, smoke),
            manifests=manifests,
            smoke=None,
        )

    failures = report.failures
    if report.passed:
        summary = f"{len(report.results)} prompt(s) faithful"
    else:
        bits = [
            (
                f"{failure.prompt_id}/{failure.tool}:"
                f"{failure.verdict.failure_class or failure.verdict.reason}"
            )
            for failure in failures
        ]
        summary = f"{len(failures)} failure(s) — " + "; ".join(bits)
    smoke = StageResult(
        name=STAGE_SMOKE,
        passed=report.passed,
        summary=summary,
        detail={
            "prompt_count": len(report.results),
            "failure_count": len(failures),
        },
    )
    stages = (check, freeze, smoke)
    return PublishReceipt(
        passed=all(stage.passed for stage in stages),
        stages=stages,
        manifests=manifests,
        smoke=report,
    )


DOGFOOD_CORPUS: tuple[CorpusPrompt, ...] = (
    CorpusPrompt(
        id="gaze-match-html-pdf",
        prompt="Match an intent to convert HTML documents into PDF.",
        tool="gaze_match",
        arguments={"intent": "html pdf convert", "node": "public"},
        required_facts=("orrery/html-to-pdf",),
    ),
    CorpusPrompt(
        id="resolve-html-to-pdf",
        prompt="Resolve the skill named orrery/html-to-pdf.",
        tool="resolve_name",
        arguments={"name": "orrery/html-to-pdf"},
        required_facts=(
            "orrery/html-to-pdf",
            "resolved",
            "mcp://orrery.lol/stars/html-to-pdf/mcp",
            "sha256:",
            "orrery-pdf-1",
        ),
    ),
    CorpusPrompt(
        id="pdf-convert-smoke",
        prompt="Convert a short HTML document to PDF via html-to-pdf.",
        tool="convert",
        arguments={"html": SMOKE_HTML},
        required_facts=("application/pdf", "page_count", "byte_length", "artifact_url", "sha256"),
    ),
    CorpusPrompt(
        id="world-time-answer-smoke",
        prompt="Answer with the live UTC time via world-time.",
        tool="answer",
        arguments={},
        required_facts=(
            "UTC",
            "live_at_call",
            "clone_warning",
            "answer",
        ),
    ),
    CorpusPrompt(
        id="source-watch-observe-smoke",
        prompt="Observe the allowlisted Python release notes source.",
        tool="observe",
        arguments={"source": "python-release-notes"},
        required_facts=(
            "python-release-notes",
            "canonical_url",
            "normalized_sha256",
            "live_at_call",
        ),
    ),
    CorpusPrompt(
        id="launch-gate-explain-smoke",
        prompt="Explain the acme/launch-gate constellation policy.",
        tool="explain_policy",
        arguments={"name": "acme/launch-gate"},
        required_facts=("gates", "repair_loop", "fan_in", "release"),
    ),
    CorpusPrompt(
        id="launch-gate-run-smoke",
        prompt="Run launch-gate on a documentation bundle.",
        tool="run",
        arguments={
            "pages": ["README.md"],
            "links": ["https://example.com/docs"],
            "examples": ["quickstart"],
            "constellation": "acme/launch-gate",
        },
        required_facts=("run_id", "secret-scan", "license", "html-to-pdf", "completed"),
    ),
    CorpusPrompt(
        id="launch-gate-status-smoke",
        prompt="Fetch the composite receipt for the latest launch-gate run.",
        tool="status",
        arguments={},
        required_facts=("completed", "chain", "secret-scan"),
    ),
)
