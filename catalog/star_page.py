"""Shared canonical human-facing Star page renderer.

Star detail pages are driven by Agent Cards (#217) plus published tool
contracts: use_when / not_for / IO / example MCP ``tools/call`` JSON / tool
one-liners — not hand-edited HTML (#219).
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from chirp import NotFound, Page, Request

from catalog import CATALOG
from catalog.agent_card import AgentCard, AgentCardIO, card_for
from catalog.console_links import PUBLISHER_DIRECT_NOTE, console_href_for
from trust.oracle import oracle_for
from trust.satisfaction import SatisfactionPillView, satisfaction_pill_for

_INTRO = {
    "cert-expiry": (
        "Watch the certificates your systems depend on and surface the ones that need "
        "attention before they become an outage."
    ),
    "html-to-pdf": (
        "Turn trusted HTML into a portable PDF artifact, with a signed receipt for every "
        "completed conversion."
    ),
    "world-time": (
        "Get current, location-aware time at call time. The answer is live evidence, not "
        "a stale bundled snapshot."
    ),
    "source-watch": (
        "Track a source for material changes and return evidence your agent can inspect "
        "before it acts."
    ),
}

#: Prefer these tool names when choosing a page example call.
_EXAMPLE_TOOL_PREFERENCE = (
    "answer",
    "convert",
    "get",
    "run",
    "observe",
    "lookup",
    "validate",
    "bind",
    "diff",
    "head",
    "inspect",
    "read",
    "submit",
    "fetch",
)


@dataclass(frozen=True, slots=True)
class StarToolLine:
    """One tool row on the star detail page."""

    name: str
    description: str
    schema_json: str
    schema_fragment: str


@dataclass(frozen=True, slots=True)
class StarPageCard:
    """Agent-actionable sections rendered on a public star page."""

    summary: str
    use_when: tuple[str, ...]
    not_for: tuple[str, ...]
    inputs: tuple[AgentCardIO, ...]
    outputs: tuple[AgentCardIO, ...]
    tools: tuple[StarToolLine, ...]
    example_tool: str
    example_call: dict[str, object]
    example_call_json: str
    resolve_href: str
    agent_card_version: str


def satisfaction_for_star(name: str, content_digest: str) -> SatisfactionPillView:
    """Demand-side aggregate pill for a star page (quiet when empty/mismatch)."""
    return satisfaction_pill_for(star_name=name, content_digest=content_digest)


def page_for_star(name: str, *, request: Request | None = None) -> Page:
    rec = CATALOG.resolve(name)
    if rec is None:
        raise NotFound(f"No resolve record for {name!r}")
    if rec.kind != "star":
        raise NotFound(f"{name!r} is a {rec.kind}, not a star")
    constellations = tuple(
        constellation
        for constellation in CATALOG.all()
        if constellation.name in rec.constellation_memberships
    )
    related = tuple(
        r for r in CATALOG.public_records() if r.kind == "star" and r.name != rec.name
    )[:3]
    layout = {}
    if request is not None:
        from pages._context import context

        layout = context(request)
    card = rec.agent_card or card_for(rec.name)
    page_card = build_star_page_card(rec.name, card, tools=rec.tools)
    intro = _intro_for(rec.short_name, card, rec.description)
    return Page(
        "star_detail.html",
        "content",
        page_block_name="content",
        rec=rec,
        oracle=oracle_for(rec),
        satisfaction=satisfaction_for_star(rec.name, rec.content_digest),
        console_href=console_href_for(rec),
        publisher_note=PUBLISHER_DIRECT_NOTE,
        intro=intro,
        card=page_card,
        constellations=constellations,
        related=related,
        page_title=f"{rec.name} — Orrery",
        footer_note="Star field guide",
        footer_meta="understand → call → verify",
        **layout,
    )


def build_star_page_card(
    name: str,
    card: AgentCard | None,
    *,
    tools: tuple[str, ...] = (),
) -> StarPageCard:
    """Project an Agent Card + published tool schemas into page view data."""
    resolve_href = f"/resolve?name={quote(name, safe='/')}"
    if card is None:
        tool_names = tools or ()
        tool_lines = tuple(
            StarToolLine(
                name=tool,
                description="Published tool on this Star's direct MCP endpoint.",
                schema_json=_pretty({"type": "object", "properties": {}}),
                schema_fragment=f"#tool-{tool}-schema",
            )
            for tool in tool_names
        )
        example_tool = tool_names[0] if tool_names else "call"
        example_call = _mcp_tools_call(example_tool, {})
        return StarPageCard(
            summary="",
            use_when=(),
            not_for=(),
            inputs=(),
            outputs=(),
            tools=tool_lines,
            example_tool=example_tool,
            example_call=example_call,
            example_call_json=_pretty(example_call),
            resolve_href=resolve_href,
            agent_card_version="",
        )

    contracts = load_tool_contracts(name)
    tool_names = tuple(card.tools) or tools
    tool_lines = tuple(_tool_line(tool, contracts.get(tool)) for tool in tool_names)
    example_tool = choose_example_tool(card, tool_names)
    arguments = example_arguments_for(example_tool, contracts.get(example_tool), card)
    example_call = _mcp_tools_call(example_tool, arguments)
    return StarPageCard(
        summary=card.summary,
        use_when=card.use_when,
        not_for=card.not_for,
        inputs=card.inputs,
        outputs=card.outputs,
        tools=tool_lines,
        example_tool=example_tool,
        example_call=example_call,
        example_call_json=_pretty(example_call),
        resolve_href=resolve_href,
        agent_card_version=card.agent_card_version,
    )


def choose_example_tool(card: AgentCard, tool_names: tuple[str, ...]) -> str:
    """Pick the most agent-useful tool for the copy-paste example."""
    if card.run_contract is not None:
        entry = card.run_contract.get("entry_tool")
        if isinstance(entry, str) and entry in tool_names:
            return entry
    for preferred in _EXAMPLE_TOOL_PREFERENCE:
        if preferred in tool_names:
            return preferred
    return tool_names[0] if tool_names else "call"


def load_tool_contracts(name: str) -> dict[str, dict[str, Any]]:
    """Load ``description`` + ``inputSchema`` per tool for a resolvable star.

    Prefers package ``tool_schemas()`` (package root or ``.contract``) when
    published; otherwise derives from the skill factory (Chirp pending tools +
    ``function_to_schema``).
    """
    from stars.builtins import builtin_registry, load_factory

    try:
        definition = builtin_registry().get(name)
    except KeyError:
        return {}

    for module_name in (definition.python_package, f"{definition.python_package}.contract"):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        raw = getattr(module, "tool_schemas", None)
        if callable(raw):
            return _normalize_contracts(raw())

    skill = load_factory(definition.skill_factory)()
    from chirp.tools.schema import function_to_schema

    contracts: dict[str, dict[str, Any]] = {}
    for pending in getattr(skill, "_pending", ()):
        schema = function_to_schema(pending.handler)
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        contracts[pending.name] = {
            "description": pending.description or f"Call {pending.name}.",
            "inputSchema": schema,
        }
    return contracts


def example_arguments_for(
    tool: str,
    contract: dict[str, Any] | None,
    card: AgentCard,
) -> dict[str, object]:
    """Build minimal example arguments that validate against the tool schema."""
    _ = tool
    schema = _coerce_schema_types(_input_schema(contract), card)
    required = _required_properties(schema)
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        properties = {}

    keys = list(required)
    if not keys and properties:
        # Schemas without ``required`` still benefit from a filled example when
        # the card marks matching inputs required.
        card_required = {item.name for item in card.inputs if item.required}
        keys = [key for key in properties if key in card_required]
    if not keys and not properties:
        if len(card.tools) <= 1:
            keys = [item.name for item in card.inputs if item.required]
        elif card.run_contract is not None:
            raw = card.run_contract.get("required_inputs")
            if isinstance(raw, list):
                keys = [item for item in raw if isinstance(item, str)]

    arguments: dict[str, object] = {}
    for key in keys:
        prop = properties.get(key)
        card_io = next((item for item in card.inputs if item.name == key), None)
        arguments[key] = _sample_value(key, prop if isinstance(prop, dict) else {}, card_io)

    if not arguments:
        for key, prop in properties.items():
            if isinstance(prop, dict) and "default" in prop:
                arguments[key] = prop["default"]

    if schema and not _arguments_validate(arguments, schema):
        arguments = {
            key: _sample_value(
                key,
                prop if isinstance(prop, dict) else {},
                None,
            )
            for key, prop in ((name, properties.get(name)) for name in required)
        }
        if not _arguments_validate(arguments, schema):
            arguments = {} if _arguments_validate({}, schema) else arguments

    return arguments


def _coerce_schema_types(schema: dict[str, Any], card: AgentCard) -> dict[str, Any]:
    """Align weak skill-inferred types with Agent Card IO when names match."""
    if not schema:
        return schema
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return schema
    card_types = {item.name: _json_type(item.type) for item in card.inputs}
    if not card_types:
        return schema
    coerced = dict(schema)
    new_properties: dict[str, Any] = {}
    for key, prop in properties.items():
        if not isinstance(prop, dict):
            new_properties[key] = prop
            continue
        updated = dict(prop)
        expected = card_types.get(key)
        if expected and updated.get("type") != expected:
            updated["type"] = expected
        new_properties[key] = updated
    coerced["properties"] = new_properties
    return coerced


def _json_type(card_type: str) -> str:
    mapping = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
        "pdf-url": "string",
        "signed-envelope": "object",
        "signed-envelope-chain": "object",
    }
    return mapping.get(card_type, "string")


def example_call_validates(name: str, card: AgentCard | None = None) -> bool:
    """Return whether the generated example validates against the tool schema."""
    resolved = card or card_for(name)
    if resolved is None:
        return False
    contracts = load_tool_contracts(name)
    tool = choose_example_tool(resolved, tuple(resolved.tools))
    contract = contracts.get(tool)
    schema = _coerce_schema_types(_input_schema(contract), resolved)
    if not schema:
        return True  # nothing published to validate against
    arguments = example_arguments_for(tool, contract, resolved)
    return _arguments_validate(arguments, schema)


def _intro_for(short_name: str, card: AgentCard | None, description: str) -> str:
    if card is not None and card.summary.strip():
        return card.summary
    return _INTRO.get(short_name, description or "A callable capability in the public Orrery.")


def _tool_line(name: str, contract: dict[str, Any] | None) -> StarToolLine:
    description = "Published tool on this Star."
    schema: dict[str, Any] = {"type": "object", "properties": {}}
    if contract is not None:
        raw_description = contract.get("description")
        if isinstance(raw_description, str) and raw_description.strip():
            description = raw_description.strip().rstrip(".")
            description = description[0].upper() + description[1:] if description else description
        schema = _input_schema(contract) or schema
    return StarToolLine(
        name=name,
        description=description,
        schema_json=_pretty(schema),
        schema_fragment=f"#tool-{name}-schema",
    )


def _normalize_contracts(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            continue
        description = value.get("description")
        schema = value.get("inputSchema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        out[name] = {
            "description": description if isinstance(description, str) else f"Call {name}.",
            "inputSchema": schema,
        }
    return out


def _input_schema(contract: dict[str, Any] | None) -> dict[str, Any]:
    if not contract:
        return {}
    schema = contract.get("inputSchema")
    return schema if isinstance(schema, dict) else {}


def _required_properties(schema: dict[str, Any]) -> list[str]:
    required = schema.get("required")
    if isinstance(required, list):
        return [item for item in required if isinstance(item, str)]
    return []


def _sample_value(
    name: str,
    prop: dict[str, Any],
    card_io: AgentCardIO | None,
) -> object:
    if "default" in prop:
        return prop["default"]
    enum = prop.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]

    type_name = prop.get("type")
    if isinstance(type_name, list):
        non_null = next((item for item in type_name if item != "null"), None)
        type_name = non_null if non_null is not None else (
            type_name[0] if type_name else "string"
        )
    if not isinstance(type_name, str) and card_io is not None:
        type_name = card_io.type

    lowered = name.lower()
    if type_name == "boolean":
        return True
    if type_name == "integer" or type_name == "number":
        minimum = prop.get("minimum")
        return minimum if isinstance(minimum, int | float) else 1
    if type_name == "array":
        return []
    if type_name == "object":
        if lowered in {"key", "row"}:
            return {"origin": "ABE", "destination": "ATL"}
        if lowered in {"left", "right", "baseline"}:
            return {"rows": [{"id": "1", "value": "a"}]}
        if lowered == "bundle":
            return {"package": "requests"}
        return {}

    # strings (default)
    pattern = prop.get("pattern")
    if isinstance(pattern, str) and pattern.startswith("^[0-9a-f]{40}"):
        return "a" * 40
    if lowered in {"question"}:
        return "What is the current UTC time?"
    if lowered in {"html"}:
        return "<p>Hello from Orrery</p>"
    if lowered in {"package"}:
        return "requests"
    if lowered in {"license_id"}:
        return "MIT"
    if lowered in {"rfc"}:
        return "8259"
    if lowered in {"pep"}:
        return "8"
    if lowered in {"section"}:
        return "1"
    if lowered in {"host"}:
        return "www.python.org"
    if lowered in {"dataset", "profile", "source", "document", "target"}:
        return prop.get("default") or "example"
    if lowered in {"decision_id"}:
        return "planner-freeze-1"
    if lowered in {"statement"}:
        return "pause for typed decision on unsupported MyST directive; do not invent MDX."
    if lowered in {"idempotency_key"}:
        return "demo-1"
    if lowered in {"run_id"}:
        return "run_demo_1"
    if lowered in {"color"}:
        return "#c4a06a"
    if lowered in {"key_column"}:
        return "id"
    if card_io is not None and card_io.note:
        return "example"
    return "example"


def _arguments_validate(arguments: dict[str, object], schema: dict[str, Any]) -> bool:
    try:
        import jsonschema
    except ImportError:
        return True
    try:
        jsonschema.validate(instance=arguments, schema=schema)
    except jsonschema.ValidationError:
        return False
    return True


def _mcp_tools_call(tool: str, arguments: dict[str, object]) -> dict[str, object]:
    return {
        "method": "tools/call",
        "params": {
            "name": tool,
            "arguments": arguments,
        },
    }


def _pretty(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=False)
