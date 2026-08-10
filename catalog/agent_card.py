"""Versioned Agent Cards — agent-actionable catalog metadata (#217).

Agent Cards are the single source of truth for *when* to call a star or
constellation, what to pass, and what comes back. They are projected into
resolve, gaze shortlists, gaze_describe, and the published JSON Schema at
``/.well-known/orrery/agent-card.schema.json``.

Progressive disclosure mirrors :class:`ProviderCard`: gaze_match carries a
compact preview (summary, ≤3 use_when bullets, short input summary); resolve
and gaze_describe carry the full card. Gaze never returns live tool bodies.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class AgentCardError(ValueError):
    """An agent card is missing required fields or fails validation."""


@dataclass(frozen=True, slots=True)
class AgentCardIO:
    """One named input or output on an agent card."""

    name: str
    type: str
    required: bool = False
    note: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
        }
        if self.note is not None:
            payload["note"] = self.note
        return payload


#: Sealed composite outcomes agents should expect from constellation runs.
DEFAULT_DISPOSITIONS: tuple[str, ...] = ("ready", "not-ready", "stale", "blocked")


@dataclass(frozen=True, slots=True)
class AgentCard:
    """Versioned, policy-first metadata for one resolvable name."""

    summary: str
    use_when: tuple[str, ...]
    not_for: tuple[str, ...]
    example_intents: tuple[str, ...]
    locality: str
    write_authority: str
    approval: str
    inputs: tuple[AgentCardIO, ...]
    outputs: tuple[AgentCardIO, ...]
    tools: tuple[str, ...]
    coverage_href: str
    agent_card_version: str = "1.0"
    run_contract: Mapping[str, object] | None = None
    graph_summary: str | None = None
    dispositions: tuple[str, ...] | None = None
    member_stars: tuple[Mapping[str, object], ...] | None = None

    def as_dict(self) -> dict[str, object]:
        """Full card for resolve / gaze_describe (no live tool payloads)."""
        payload: dict[str, object] = {
            "agent_card_version": self.agent_card_version,
            "summary": self.summary,
            "use_when": list(self.use_when),
            "not_for": list(self.not_for),
            "example_intents": list(self.example_intents),
            "locality": self.locality,
            "write_authority": self.write_authority,
            "approval": self.approval,
            "inputs": [item.as_dict() for item in self.inputs],
            "outputs": [item.as_dict() for item in self.outputs],
            "tools": list(self.tools),
            "coverage_href": self.coverage_href,
        }
        if self.run_contract is not None:
            payload["run_contract"] = dict(self.run_contract)
        if self.graph_summary is not None:
            payload["graph_summary"] = self.graph_summary
        if self.dispositions is not None:
            payload["dispositions"] = list(self.dispositions)
        if self.member_stars is not None:
            payload["member_stars"] = [dict(item) for item in self.member_stars]
        return payload

    def gaze_preview(self) -> dict[str, object]:
        """Compact progressive-disclosure fields for gaze_match hits."""
        return {
            "summary": self.summary,
            "use_when": list(self.use_when[:3]),
            "inputs_summary": inputs_summary(self),
        }

    def searchable_text(self) -> str:
        """Concatenated text indexed by gaze match/search."""
        parts = [self.summary, *self.use_when, *self.example_intents]
        return " ".join(parts).lower()


def inputs_summary(card: AgentCard) -> str:
    """Short human/agent-facing input blurb for gaze shortlists.

    Prefer ``run_contract.required_inputs`` / ``optional_inputs`` when present
    so constellation hits advertise what ``run`` expects (#220).
    """
    if card.run_contract is not None:
        required = [str(name) for name in (card.run_contract.get("required_inputs") or [])]
        optional = [str(name) for name in (card.run_contract.get("optional_inputs") or [])]
        bits = [f"{name}*" for name in required]
        bits.extend(optional)
        return ", ".join(bits) if bits else "no required inputs"
    if not card.inputs:
        return "no inputs"
    bits: list[str] = []
    for item in card.inputs:
        label = item.name
        if item.required:
            label = f"{label}*"
        bits.append(label)
    return ", ".join(bits)


def _io(
    name: str,
    type_: str,
    *,
    required: bool = False,
    note: str | None = None,
) -> AgentCardIO:
    return AgentCardIO(name=name, type=type_, required=required, note=note)


def member_stars_from_policy(name: str) -> tuple[dict[str, object], ...]:
    """Derive member-star roles from the constellation policy graph."""
    from .constellation import policy_for

    graph = policy_for(name)
    if graph is None:
        return ()
    members: list[dict[str, object]] = []
    for node in graph.nodes:
        if node.node_kind == "composite":
            continue
        members.append(
            {
                "name": node.star_ref or node.id,
                "role": node.node_kind,
                "label": node.label,
            }
        )
    return tuple(members)


def _card(
    *,
    summary: str,
    use_when: tuple[str, ...],
    not_for: tuple[str, ...],
    example_intents: tuple[str, ...],
    tools: tuple[str, ...],
    coverage_slug: str,
    inputs: tuple[AgentCardIO, ...] = (),
    outputs: tuple[AgentCardIO, ...] = (),
    locality: str = "orrery-hosted",
    write_authority: str = "read-only",
    approval: str = "not-required",
    run_contract: Mapping[str, object] | None = None,
    graph_summary: str | None = None,
    dispositions: tuple[str, ...] | None = None,
    member_stars: tuple[Mapping[str, object], ...] | None = None,
) -> AgentCard:
    return AgentCard(
        summary=summary,
        use_when=use_when,
        not_for=not_for,
        example_intents=example_intents,
        locality=locality,
        write_authority=write_authority,
        approval=approval,
        inputs=inputs,
        outputs=outputs,
        tools=tools,
        coverage_href=f"/coverage/{coverage_slug}",
        run_contract=run_contract,
        graph_summary=graph_summary,
        dispositions=dispositions,
        member_stars=member_stars,
    )


#: Signed envelope output shared by most public stars.
_ENVELOPE = (_io("envelope", "signed-envelope"),)
_CONTENT = (_io("content", "string"), *_ENVELOPE)


def validate_agent_card(card: AgentCard, *, name: str | None = None) -> None:
    """Reject incomplete or malformed agent cards (CI / sync guard)."""
    where = f" for {name}" if name else ""
    if not card.agent_card_version.strip():
        raise AgentCardError(f"agent_card_version must be non-empty{where}")
    if not card.summary.strip():
        raise AgentCardError(f"summary must be non-empty{where}")
    if not card.use_when:
        raise AgentCardError(f"use_when must list at least one bullet{where}")
    if any(not bullet.strip() for bullet in card.use_when):
        raise AgentCardError(f"use_when bullets must be non-empty{where}")
    if not card.not_for:
        raise AgentCardError(f"not_for must list at least one boundary{where}")
    if not card.example_intents:
        raise AgentCardError(f"example_intents must list at least one intent{where}")
    if not card.locality.strip():
        raise AgentCardError(f"locality must be non-empty{where}")
    if not card.write_authority.strip():
        raise AgentCardError(f"write_authority must be non-empty{where}")
    if not card.approval.strip():
        raise AgentCardError(f"approval must be non-empty{where}")
    if not card.tools:
        raise AgentCardError(f"tools must list at least one tool{where}")
    if not card.coverage_href.startswith("/coverage/"):
        raise AgentCardError(f"coverage_href must start with /coverage/{where}")
    for item in (*card.inputs, *card.outputs):
        if not item.name.strip() or not item.type.strip():
            raise AgentCardError(f"inputs/outputs need name and type{where}")


def agent_card_json_schema() -> dict[str, Any]:
    """JSON Schema (draft 2020-12) for Agent Card v1."""
    io_schema = {
        "type": "object",
        "required": ["name", "type"],
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "type": {"type": "string", "minLength": 1},
            "required": {"type": "boolean"},
            "note": {"type": "string"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://orrery.lol/.well-known/orrery/agent-card.schema.json",
        "title": "Orrery Agent Card",
        "description": (
            "Agent-actionable metadata for a public star or constellation. "
            "Informational shortlist data — the agent remains the semantic router."
        ),
        "type": "object",
        "required": [
            "agent_card_version",
            "summary",
            "use_when",
            "not_for",
            "example_intents",
            "locality",
            "write_authority",
            "approval",
            "inputs",
            "outputs",
            "tools",
            "coverage_href",
        ],
        "additionalProperties": False,
        "properties": {
            "agent_card_version": {"type": "string", "const": "1.0"},
            "summary": {"type": "string", "minLength": 1},
            "use_when": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "not_for": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "example_intents": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "locality": {"type": "string", "minLength": 1},
            "write_authority": {"type": "string", "minLength": 1},
            "approval": {"type": "string", "minLength": 1},
            "inputs": {"type": "array", "items": io_schema},
            "outputs": {"type": "array", "items": io_schema},
            "tools": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "coverage_href": {
                "type": "string",
                "pattern": "^/coverage/",
            },
            "run_contract": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "entry_tool": {"type": "string"},
                    "required_inputs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "optional_inputs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "composite_output": {"type": "string"},
                    "input_bundle": {"type": "object"},
                },
            },
            "graph_summary": {"type": "string"},
            "dispositions": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
            "member_stars": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "role"],
                    "additionalProperties": True,
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "label": {"type": "string"},
                    },
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Registry — parallel to star.toml; do not mass-rewrite package blurbs (#218)
# ---------------------------------------------------------------------------


_STAR_CARDS: dict[str, AgentCard] = {
    "orrery/gh-file-at-ref": _card(
        summary="Fetch a public repo file pinned to an exact commit SHA.",
        use_when=(
            "You need file contents at a specific revision for review or diffing",
            "You are building evidence that must not drift from a pinned commit",
            "You want a bounded allowlisted GitHub file, not arbitrary paths",
        ),
        not_for=(
            "Private repositories",
            "Repos outside the published allowlist",
            "Branch or tag refs that are not a full 40-char commit SHA",
        ),
        example_intents=(
            "get README at commit",
            "fetch changelog at sha",
            "pinned file from github",
        ),
        tools=("get",),
        coverage_slug="gh-file-at-ref",
        inputs=(
            _io("target", "string", required=True, note="allowlisted named file target"),
            _io("ref", "string", required=True, note="full 40-char commit SHA"),
        ),
        outputs=_CONTENT,
    ),
    "orrery/world-time": _card(
        summary="Live UTC truth at call time; offline clones are stale.",
        use_when=(
            "You need a fresh UTC timestamp sealed in an Envelope",
            "You are proving that a clone cannot mint live clock evidence",
            "You want a liveness witness for a larger policy graph",
        ),
        not_for=(
            "Historical time lookups",
            "Non-UTC local wall clocks",
            "Cached or offline clock packages",
        ),
        example_intents=("live utc now", "current time sealed", "fresh clock evidence"),
        tools=("fetch", "get", "answer"),
        coverage_slug="world-time",
        outputs=(
            _io("dateTime", "string", note="UTC datetime from the live clock"),
            *_ENVELOPE,
        ),
    ),
    "orrery/source-watch": _card(
        summary="Live official-source evidence, digest comparison, and bounded answers.",
        use_when=(
            "You need a fresh digest of an allowlisted official source",
            "You want to compare current content to a prior digest",
            "You need a bounded extractive answer with live source evidence",
        ),
        not_for=(
            "Arbitrary URLs outside the allowlist",
            "Open-ended web search",
            "Mutating remote sources",
        ),
        example_intents=(
            "observe python release notes",
            "diff official source digest",
            "answer from live source",
        ),
        tools=("observe", "diff", "answer"),
        coverage_slug="source-watch",
        inputs=(
            _io("source", "string", note="allowlisted source id"),
            _io("since_digest", "string", note="prior digest for diff"),
            _io("question", "string", note="required for answer"),
        ),
        outputs=(
            _io("digest", "string"),
            _io("changed", "boolean"),
            _io("answer", "string"),
            *_ENVELOPE,
        ),
    ),
    "orrery/html-to-pdf": _card(
        summary="Render simple HTML to a downloadable PDF with signed receipts.",
        use_when=(
            "You need a short-lived PDF artifact from trusted HTML",
            "You want a signed convert receipt for document evidence",
            "You are queueing a managed PDF run and polling for the result",
        ),
        not_for=(
            "Untrusted HTML with active content",
            "Complex CSS/layout engines",
            "Long-term PDF hosting",
        ),
        example_intents=("html to pdf", "render receipt pdf", "convert html document"),
        tools=("convert", "submit", "result", "health"),
        coverage_slug="html-to-pdf",
        inputs=(
            _io("html", "string", required=True),
            _io("idempotency_key", "string", note="required for submit"),
            _io("run_id", "string", note="required for result"),
        ),
        outputs=(
            _io("artifact", "pdf-url"),
            _io("run_id", "string"),
            *_ENVELOPE,
        ),
    ),
    "orrery/http-head": _card(
        summary="Fresh HTTP metadata for named allowlisted official targets.",
        use_when=(
            "You need status/headers for an allowlisted official URL",
            "You are checking freshness without downloading a body",
        ),
        not_for=("Arbitrary URLs", "POST or mutating requests", "Full body retrieval"),
        example_intents=("http head python docs", "fresh headers for target"),
        tools=("head",),
        coverage_slug="http-head",
        inputs=(_io("target", "string", note="allowlisted named target"),),
        outputs=(_io("status", "integer"), _io("headers", "object"), *_ENVELOPE),
    ),
    "orrery/well-known": _card(
        summary="Bounded fresh slices of named official discovery documents.",
        use_when=(
            "You need a slice of an allowlisted well-known document",
            "You are checking discovery metadata without fetching the whole file",
        ),
        not_for=("Private discovery docs", "Arbitrary paths", "Write/update of discovery files"),
        example_intents=("read well-known document", "fresh discovery slice"),
        tools=("read",),
        coverage_slug="well-known",
        inputs=(_io("document", "string", note="allowlisted document id"),),
        outputs=_CONTENT,
    ),
    "orrery/cert-expiry": _card(
        summary="TLS certificate expiry metadata for named allowlisted hosts.",
        use_when=(
            "You need notAfter / SANs for an allowlisted HTTPS host",
            "You are assembling expiry evidence before a renew decision",
        ),
        not_for=("Hosts outside the allowlist", "Certificate issuance", "Private PKI endpoints"),
        example_intents=("cert expiry for host", "tls notAfter inspect"),
        tools=("inspect",),
        coverage_slug="cert-expiry",
        inputs=(_io("host", "string", note="allowlisted HTTPS host"),),
        outputs=(
            _io("not_after", "string"),
            _io("subject", "string"),
            *_ENVELOPE,
        ),
    ),
    "orrery/rfc-section": _card(
        summary="Bounded sections from named allowlisted RFC Editor documents.",
        use_when=(
            "You need a named RFC section, not the whole document",
            "You want bounded normative text for reasoning",
        ),
        not_for=("RFCs outside the allowlist", "Full-document dumps", "Editing RFCs"),
        example_intents=("rfc section text", "get allowlisted rfc clause"),
        tools=("get",),
        coverage_slug="rfc-section",
        inputs=(
            _io("rfc", "string", required=True),
            _io("section", "string", required=True),
        ),
        outputs=_CONTENT,
    ),
    "orrery/pep-section": _card(
        summary="Bounded sections from named canonical Python PEP documents.",
        use_when=(
            "You need a named PEP section for language/runtime guidance",
            "You want bounded PEP text rather than a full download",
        ),
        not_for=("PEPs outside the allowlist", "Full PEP dumps", "Editing PEPs"),
        example_intents=("pep section text", "get python pep clause"),
        tools=("get",),
        coverage_slug="pep-section",
        inputs=(
            _io("pep", "string", required=True),
            _io("section", "string", required=True),
        ),
        outputs=_CONTENT,
    ),
    "orrery/spdx-license": _card(
        summary="Bounded SPDX license text and metadata for named allowlisted identifiers.",
        use_when=(
            "You need SPDX license text for an allowlisted identifier",
            "You are assembling license evidence for a gate",
        ),
        not_for=("Unknown SPDX IDs", "Custom license drafting", "License approval decisions"),
        example_intents=("spdx license text", "get mit license metadata"),
        tools=("get",),
        coverage_slug="spdx-license",
        inputs=(_io("license_id", "string", required=True),),
        outputs=(_io("license_text", "string"), _io("metadata", "object"), *_ENVELOPE),
    ),
    "orrery/csv-url": _card(
        summary="Bounded typed rows from named allowlisted public CSV datasets.",
        use_when=(
            "You need a fresh sample of an allowlisted public CSV",
            "You want typed rows without scraping arbitrary URLs",
        ),
        not_for=("Arbitrary CSV URLs", "Unbounded downloads", "Mutating datasets"),
        example_intents=("get flights csv sample", "fresh allowlisted csv rows"),
        tools=("get",),
        coverage_slug="csv-url",
        inputs=(_io("dataset", "string", required=True),),
        outputs=(_io("rows", "array"), *_ENVELOPE),
    ),
    "orrery/row-lookup": _card(
        summary="Exact typed row lookup in a named allowlisted public CSV dataset.",
        use_when=(
            "You need one exact row by key from an allowlisted dataset",
            "You want typed lookup evidence without scanning the whole file",
        ),
        not_for=("Fuzzy search", "Datasets outside the allowlist", "Bulk exports"),
        example_intents=("lookup flight row", "exact csv key lookup"),
        tools=("lookup",),
        coverage_slug="row-lookup",
        inputs=(
            _io("dataset", "string", required=True),
            _io("key", "object", required=True, note="origin/destination fields"),
        ),
        outputs=(_io("row", "object"), *_ENVELOPE),
    ),
    "orrery/row-validate": _card(
        summary="Pure validation of one row against a named static source-aligned profile.",
        use_when=(
            "You need to validate a small row against a known profile",
            "You want schema errors without network I/O",
        ),
        not_for=("Profiles outside the allowlist", "Large batch validation", "Data mutation"),
        example_intents=("validate flight row", "check row against profile"),
        tools=("validate",),
        coverage_slug="row-validate",
        inputs=(
            _io("profile", "string", required=True),
            _io("row", "object", required=True),
        ),
        outputs=(_io("ok", "boolean"), _io("errors", "array"), *_ENVELOPE),
    ),
    "orrery/table-diff": _card(
        summary="Pure bounded comparison of two caller-provided tabular snapshots.",
        use_when=(
            "You have two small snapshots and need a keyed diff",
            "You want a deterministic table verdict without fetching data",
        ),
        not_for=("Huge tables", "Fuzzy matching", "Live dataset fetches"),
        example_intents=("diff two table snapshots", "compare keyed rows"),
        tools=("diff",),
        coverage_slug="table-diff",
        inputs=(
            _io("left", "object", required=True),
            _io("right", "object", required=True),
            _io("key_column", "string", required=True),
        ),
        outputs=(_io("verdict", "object"), *_ENVELOPE),
    ),
    "orrery/table-fresh": _card(
        summary="Fresh bounded flights sample and deterministic table-diff verdict.",
        use_when=(
            "You need live CSV sample evidence compared to a baseline",
            "You want a freshness verdict sealed for a policy step",
        ),
        not_for=("Arbitrary datasets", "Unbounded samples", "Deploy approval"),
        example_intents=("freshen flights sample", "table freshness verdict"),
        tools=("run",),
        coverage_slug="table-fresh",
        inputs=(_io("baseline", "object", required=True),),
        outputs=(_io("verdict", "object"), *_ENVELOPE),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["baseline"],
            "optional_inputs": [],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "baseline": {
                    "type": "object",
                    "required": True,
                    "note": "caller-provided tabular baseline for table-diff",
                }
            },
        },
        graph_summary="csv-url sample → table-diff → fresh verdict",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/table-fresh"),
    ),
    "orrery/pypi-release": _card(
        summary="Bounded current release metadata for named allowlisted PyPI packages.",
        use_when=(
            "You need the current PyPI release metadata for an allowlisted package",
            "You are gathering release evidence before reasoning",
        ),
        not_for=("Packages outside the allowlist", "Uploading packages", "Dependency resolution"),
        example_intents=("pypi latest version", "allowlisted package release"),
        tools=("get",),
        coverage_slug="pypi-release",
        inputs=(_io("package", "string", required=True),),
        outputs=(_io("release", "object"), *_ENVELOPE),
    ),
    "orrery/npm-release": _card(
        summary="Bounded latest dist-tag metadata for named allowlisted npm packages.",
        use_when=(
            "You need latest dist-tag metadata for an allowlisted npm package",
            "You are gathering release evidence before reasoning",
        ),
        not_for=("Packages outside the allowlist", "Publishing packages", "Lockfile resolution"),
        example_intents=("npm latest dist-tag", "allowlisted npm release"),
        tools=("get",),
        coverage_slug="npm-release",
        inputs=(_io("package", "string", required=True),),
        outputs=(_io("dist_tags", "object"), *_ENVELOPE),
    ),
    "orrery/gh-release-notes": _card(
        summary="Bounded latest release notes for named allowlisted GitHub repositories.",
        use_when=(
            "You need the latest release notes for an allowlisted repo",
            "You want to compare notes against a prior body digest",
        ),
        not_for=("Private repos", "Repos outside the allowlist", "Creating releases"),
        example_intents=("github release notes", "observe latest release body"),
        tools=("observe",),
        coverage_slug="gh-release-notes",
        inputs=(
            _io("target", "string", required=True),
            _io("prior_body_digest", "string"),
        ),
        outputs=(_io("body", "string"), _io("digest", "string"), *_ENVELOPE),
    ),
    "orrery/ship-check": _card(
        summary="Bounded release, freshness, and UTC evidence for reasoning.",
        use_when=(
            "You need combined release + source + UTC evidence before reasoning",
            "You want a sealed ship-check bundle, not a deploy button",
        ),
        not_for=("Deploy approval", "Mutating registries", "Packages outside allowlists"),
        example_intents=("ship check evidence", "release freshness utc bundle"),
        tools=("run",),
        coverage_slug="ship-check",
        inputs=(
            _io("package", "string", required=True),
            _io("source_digest", "string"),
        ),
        outputs=(_io("evidence", "object"), *_ENVELOPE),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["package"],
            "optional_inputs": ["source_digest"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "package": {"type": "string", "required": True},
                "source_digest": {"type": "string", "required": False},
            },
        },
        graph_summary="release metadata → source-watch → world-time → reason",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/ship-check"),
    ),
    "orrery/stale-proof": _card(
        summary="Fresh UTC plus official Python release-note digest evidence.",
        use_when=(
            "You need to prove a clone cannot mint live truth",
            "You want sealed UTC + official-source digest evidence together",
        ),
        not_for=("Historical clocks", "Arbitrary sources", "Deploy approval"),
        example_intents=("stale proof seal", "live utc and release notes digest"),
        tools=("run",),
        coverage_slug="stale-proof",
        inputs=(_io("source_digest", "string"),),
        outputs=(_io("evidence", "object"), *_ENVELOPE),
        run_contract={
            "entry_tool": "run",
            "required_inputs": [],
            "optional_inputs": ["source_digest"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "source_digest": {
                    "type": "string",
                    "required": False,
                    "note": "optional prior digest for source-watch diff",
                }
            },
        },
        graph_summary="world-time → source-watch → seal",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=member_stars_from_policy("orrery/stale-proof"),
    ),
    "orrery/csv-report": _card(
        summary="Queue a durable CSV report on Orrery's managed CPU worker.",
        use_when=(
            "You need an async CSV report run with a durable receipt",
            "You are submitting rows and polling for a signed result",
        ),
        not_for=("Synchronous inline renders", "Unbounded row sets", "Direct filesystem writes"),
        example_intents=("queue csv report", "managed csv worker result"),
        tools=("submit", "result"),
        coverage_slug="csv-report",
        inputs=(
            _io("rows", "array", required=True, note="required for submit"),
            _io("idempotency_key", "string", required=True, note="required for submit"),
            _io("run_id", "string", note="required for result"),
        ),
        outputs=(_io("run_id", "string"), *_ENVELOPE),
        write_authority="managed-worker-write",
    ),
    "orrery/image-transform": _card(
        summary="Queue a safe PNG transform on Orrery's managed CPU worker.",
        use_when=(
            "You need a bounded PNG color-fill transform via managed CPU",
            "You are submitting work and polling for a signed result",
        ),
        not_for=("Arbitrary image codecs", "Unbounded uploads", "Direct filesystem writes"),
        example_intents=("queue png transform", "managed image worker result"),
        tools=("submit", "result"),
        coverage_slug="image-transform",
        inputs=(
            _io("color", "string", required=True, note="required for submit"),
            _io("idempotency_key", "string", required=True, note="required for submit"),
            _io("run_id", "string", note="required for result"),
        ),
        outputs=(_io("run_id", "string"), *_ENVELOPE),
        write_authority="managed-worker-write",
    ),
}

_CONSTELLATION_CARDS: dict[str, AgentCard] = {
    "acme/release-gate": _card(
        summary="Private constellation entry for release gating demos.",
        use_when=(
            "You are exploring a private constellation MCP node",
            "You need run/status/explain_policy against a gated graph",
        ),
        not_for=("Public sky calls without namespace access", "Treating this as deploy approval"),
        example_intents=("run release gate", "explain release policy"),
        tools=("run", "status", "explain_policy"),
        coverage_slug="acme-release-gate",
        inputs=(_io("bundle", "object", required=True),),
        outputs=(_io("chain", "signed-envelope-chain"),),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["bundle"],
            "optional_inputs": ["targets"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "pages": {"type": "array", "items": "string"},
                "links": {"type": "array", "items": "string"},
                "examples": {"type": "array", "items": "string"},
            },
        },
        graph_summary="private release gates → status → explain_policy",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=(),
        locality="namespace-private",
        approval="namespace-gated",
    ),
    "acme/launch-gate": _card(
        summary="Ship policy graph — gates, repair loop, and fan-in disposition.",
        use_when=(
            "You need a composite launch-gate run over a policy graph",
            "You want explain_policy for gates, loops, and fan-in",
            "You are demoing constellation orchestration, not a single star",
        ),
        not_for=(
            "Public-only agents without acme namespace access",
            "Skipping human-approve witnesses",
            "Treating composite PASS as production deploy authority",
        ),
        example_intents=("run launch gate", "explain ship policy", "constellation status"),
        tools=("run", "status", "explain_policy"),
        coverage_slug="acme-launch-gate",
        inputs=(
            _io("bundle", "object", required=True, note="Doc Bundle: pages, links, examples"),
            _io("targets", "array"),
        ),
        outputs=(_io("chain", "signed-envelope-chain"),),
        run_contract={
            "entry_tool": "run",
            "required_inputs": ["bundle"],
            "optional_inputs": ["targets", "constellation"],
            "composite_output": "signed-envelope-chain",
            "input_bundle": {
                "pages": {"type": "array", "items": "string"},
                "links": {"type": "array", "items": "string"},
                "examples": {"type": "array", "items": "string"},
            },
        },
        graph_summary="secret-scan → license → html-to-pdf → human-approve fan-in",
        dispositions=DEFAULT_DISPOSITIONS,
        member_stars=member_stars_from_policy("acme/launch-gate"),
        locality="namespace-private",
        approval="human-approve-witness",
    ),
}

AGENT_CARDS: dict[str, AgentCard] = {**_STAR_CARDS, **_CONSTELLATION_CARDS}


def card_for(name: str) -> AgentCard | None:
    """Return the registered agent card for a resolvable name, if any."""
    return AGENT_CARDS.get(name)


def require_card(name: str) -> AgentCard:
    """Return a validated card or raise if missing/invalid."""
    card = card_for(name)
    if card is None:
        raise AgentCardError(f"missing agent card for {name!r}")
    validate_agent_card(card, name=name)
    return card


def assert_registry_complete(names: tuple[str, ...] | list[str]) -> None:
    """CI guard: every required public name has a valid agent card."""
    missing: list[str] = []
    invalid: list[str] = []
    for name in names:
        card = card_for(name)
        if card is None:
            missing.append(name)
            continue
        try:
            validate_agent_card(card, name=name)
        except AgentCardError as error:
            invalid.append(f"{name}: {error}")
    if missing or invalid:
        parts: list[str] = []
        if missing:
            parts.append(f"missing cards: {missing}")
        if invalid:
            parts.append(f"invalid cards: {invalid}")
        raise AgentCardError("; ".join(parts))


def required_public_card_names() -> tuple[str, ...]:
    """Names that must carry agent cards (builtin stars + constellation seeds)."""
    from stars._core.registry import load_builtin_star_definition
    from stars.builtins import BUILTIN_STAR_PACKAGES

    from .fixtures import CONSTELLATION_SEEDS

    star_names = tuple(
        sorted(load_builtin_star_definition(package).name for package in BUILTIN_STAR_PACKAGES)
    )
    constellation_names = tuple(record.name for record in CONSTELLATION_SEEDS)
    return star_names + constellation_names
