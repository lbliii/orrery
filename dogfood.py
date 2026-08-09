"""Temporary dogfood skills for the Orrery host — N wrapped ``chirp.skill`` apps.

Gaze / Resolve / html-to-pdf / world-time / source-watch share one aggregated ``/mcp`` with
unique tool names. Gaze discovers skills (``gaze_match`` / ``gaze_search`` /
``gaze_describe`` / ``gaze_list_constellations``); Resolve returns Skill DNS
via ``resolve_name``; html-to-pdf is the Call / Envelope plumbing demo (issues
#25-#27); world-time is the Wave 1 reactive expertise spike (#37) — live UTC
payload sealed at call time. Source Watch observes an allowlisted official
source and seals current evidence or a bounded answer at call time (#51).

Each skill has a golden corpus entry that passes the publish oracle
(``run_publish_gate`` / smoke harness).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from chirp.skill import Envelope, Skill, verify_envelope
from chirp.skill.smoke import CorpusPrompt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog import CATALOG
from catalog.constellation_run import explain_policy, run_constellation, status_for_run
from source_watch import ANSWER_MAX_CHARS
from source_watch import answer as source_watch_answer
from source_watch import diff as source_watch_diff
from source_watch import observe as source_watch_observe

#: How many dogfood skills this host mounts (Foundation epic #2 + Waves 1/2).
N_DOGFOOD_SKILLS = 6

#: Smoke HTML used by the star detail receipt and corpus.
SMOKE_HTML = "<!doctype html><html><body><h1>Orrery</h1></body></html>"

#: Public UTC clock used by the reactive world-time star (stdlib urllib).
WORLD_TIME_URL = "https://timeapi.io/api/Time/current/zone?timeZone=UTC"

#: Why an offline clone fails the value test (README + star page + payload).
WORLD_TIME_CLONE_WARNING = (
    "Offline clones cannot mint a fresh UTC instant from the public clock API; "
    "any baked-in datetime is stale by definition. Value is live truth at call time."
)

_html_to_pdf_skill: Skill | None = None
_world_time_skill: Skill | None = None
_source_watch_skill: Skill | None = None

def _load_or_generate_key(env_name: str) -> Ed25519PrivateKey:
    raw = os.environ.get(env_name, "").strip()
    if raw:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
    return Ed25519PrivateKey.generate()


def fetch_live_utc() -> dict[str, object]:
    """Pull a live UTC clock reading (injectable via ``ORRERY_WORLD_TIME_JSON``).

    Tests/CI set ``ORRERY_WORLD_TIME_JSON`` to a deterministic fixture so smoke
    does not depend on upstream availability. Production leaves it unset and
    hits :data:`WORLD_TIME_URL` at call time.
    """
    override = os.environ.get("ORRERY_WORLD_TIME_JSON", "").strip()
    if override:
        data = json.loads(override)
        if not isinstance(data, dict):
            msg = "ORRERY_WORLD_TIME_JSON must be a JSON object"
            raise ValueError(msg)
        return _world_time_payload(data, source="fixture:ORRERY_WORLD_TIME_JSON")

    req = urllib.request.Request(
        WORLD_TIME_URL,
        headers={
            "User-Agent": "orrery-world-time/0.1 (+https://github.com/lbliii/orrery)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "error": "upstream_unreachable",
            "detail": str(exc),
            "timezone": "UTC",
            "source": WORLD_TIME_URL,
            "live_at_call": True,
            "clone_warning": WORLD_TIME_CLONE_WARNING,
        }
    if not isinstance(raw, dict):
        return {
            "error": "upstream_malformed",
            "timezone": "UTC",
            "source": WORLD_TIME_URL,
            "live_at_call": True,
            "clone_warning": WORLD_TIME_CLONE_WARNING,
        }
    return _world_time_payload(raw, source=WORLD_TIME_URL)


def _world_time_payload(raw: dict[str, Any], *, source: str) -> dict[str, object]:
    datetime_s = raw.get("dateTime") or raw.get("datetime") or raw.get("utc_datetime")
    return {
        "timezone": str(raw.get("timeZone") or raw.get("timezone") or "UTC"),
        "datetime": datetime_s,
        "date": raw.get("date"),
        "time": raw.get("time"),
        "day_of_week": raw.get("dayOfWeek") or raw.get("day_of_week"),
        "source": source,
        "live_at_call": True,
        "clone_warning": WORLD_TIME_CLONE_WARNING,
    }


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
        description="Match an intent to ranked catalog hits (name, blurb, endpoint, price)",
    )
    def gaze_match(intent: str, node: str = "public") -> dict[str, object]:
        hits = CATALOG.match(intent, node=node or "public")
        return {
            "intent": intent,
            "node": node or "public",
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
        }

    @skill.tool(
        "gaze_search",
        description="Search catalog names and descriptions by substring",
    )
    def gaze_search(query: str, node: str = "") -> dict[str, object]:
        hits = CATALOG.search(query, node=node or None)
        return {
            "query": query,
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
        }

    @skill.tool(
        "gaze_describe",
        description="Describe a skill by name (manifest metadata, no execution)",
    )
    def gaze_describe(name: str) -> dict[str, object]:
        return CATALOG.describe(name)

    @skill.tool(
        "gaze_list_constellations",
        description="List constellation-kind records in the catalog",
    )
    def gaze_list_constellations(node: str = "") -> dict[str, object]:
        hits = CATALOG.list_constellations(node=node or None)
        return {
            "hits": [h.as_dict() for h in hits],
            "status": "ok",
        }

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
        record = CATALOG.resolve(name)
        if record is None:
            return {"error": "not_found", "name": name, "status": "not_found"}
        payload = record.as_dict()
        payload["status"] = "resolved"
        return payload

    return skill


def build_html_to_pdf_skill(*, private_key: Any | None = None) -> Skill:
    """html-to-pdf — stub HTML→PDF convert + health (Call / Envelope demo)."""
    private = private_key or _load_or_generate_key("ORRERY_PDF_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "html-to-pdf",
        version="1.2.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_PDF_KEY_ID", "orrery-pdf-1"),
        public_key=public,
    )

    @skill.tool("convert", description="Convert HTML to PDF (stub; real Envelope)")
    def convert(html: str) -> dict[str, object]:
        raw = html.encode("utf-8")
        # Stub metrics — enough for digest + Envelope proof without a PDF engine.
        pages = max(1, (len(raw) + 1499) // 1500)
        return {
            "pages": pages,
            "bytes_hint": len(raw) + 1024,
            "content_type": "application/pdf",
        }

    @skill.tool("health", description="html-to-pdf readiness probe")
    def health() -> dict[str, str]:
        return {"status": "ok", "skill": "html-to-pdf"}

    return skill


def build_world_time_skill(*, private_key: Any | None = None) -> Skill:
    """world-time — live UTC clock sealed in an Envelope at call time (#37)."""
    private = private_key or _load_or_generate_key("ORRERY_WORLD_TIME_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "world-time",
        version="0.1.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_WORLD_TIME_KEY_ID", "orrery-world-time-1"),
        public_key=public,
    )

    @skill.tool(
        "fetch",
        description="Fetch live UTC from the public clock API (signed at call time)",
    )
    def fetch() -> dict[str, object]:
        return fetch_live_utc()

    @skill.tool(
        "get",
        description="Get the live UTC reading (same live source as fetch)",
    )
    def get() -> dict[str, object]:
        return fetch_live_utc()

    @skill.tool(
        "answer",
        description="Answer with the live UTC datetime sealed in an Envelope",
    )
    def answer() -> dict[str, object]:
        live = fetch_live_utc()
        when = live.get("datetime") or live.get("error") or "unknown"
        return {
            **live,
            "answer": f"UTC now is {when}",
        }

    return skill


def build_source_watch_skill(*, private_key: Any | None = None) -> Skill:
    """source-watch — evidence-backed monitoring of an allowlisted source."""
    private = private_key or _load_or_generate_key("ORRERY_SOURCE_WATCH_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "source-watch",
        version="0.1.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_SOURCE_WATCH_KEY_ID", "orrery-source-watch-1"),
        public_key=public,
    )

    @skill.tool(
        "observe",
        description="Fetch an allowlisted source and record signed digest evidence",
    )
    def observe(source: str = "python-release-notes") -> dict[str, object]:
        return source_watch_observe(source)

    @skill.tool("diff", description="Fetch now and compare normalized content to a known digest")
    def diff(source: str = "python-release-notes", since_digest: str = "") -> dict[str, object]:
        return source_watch_diff(source, since_digest)

    # ``answer`` is already owned by world-time on the aggregated MCP host.
    # Keep Source Watch's verb explicit while retaining the skill-local contract.
    @skill.tool(
        "source_watch_answer",
        description="Answer from a freshly fetched official source with bounded evidence",
    )
    def answer(
        question: str,
        source: str = "python-release-notes",
        max_chars: int = ANSWER_MAX_CHARS,
    ) -> dict[str, object]:
        return source_watch_answer(question, source, max_chars)

    return skill


def build_launch_gate_skill(*, private_key: Any | None = None) -> Skill:
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

    @skill.tool(
        "run",
        description="Execute the constellation on a Doc Bundle (pages, links, examples)",
    )
    def run(
        pages: list[str] | None = None,
        links: list[str] | None = None,
        examples: list[str] | None = None,
        constellation: str = "acme/launch-gate",
    ) -> dict[str, object]:
        bundle = {
            "pages": list(pages or []),
            "links": list(links or []),
            "examples": list(examples or []),
        }
        return run_constellation(
            bundle,
            constellation=constellation,
            skill_name=skill.name,
            skill_version=skill.version,
            key_id=skill.key_id,
            private_key=private,
        )

    @skill.tool(
        "status",
        description="Composite receipt / in-flight chain for a constellation run",
    )
    def status(run_id: str = "") -> dict[str, object]:
        return status_for_run(run_id)

    @skill.tool(
        "explain_policy",
        description="Gates, repair loops, and fan-in in plain language",
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


def build_dogfood_skills() -> tuple[Skill, ...]:
    """Return the N dogfood skills in mount order."""
    skills = (
        build_gaze_skill(),
        build_resolve_skill(),
        get_html_to_pdf_skill(),
        get_world_time_skill(),
        get_source_watch_skill(),
        build_launch_gate_skill(),
    )
    assert len(skills) == N_DOGFOOD_SKILLS
    return skills


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
            "mcp://orrery.dev/s/html-to-pdf",
            "sha256:",
            "orrery-pdf-1",
        ),
    ),
    CorpusPrompt(
        id="pdf-convert-smoke",
        prompt="Convert a short HTML document to PDF via html-to-pdf.",
        tool="convert",
        arguments={"html": SMOKE_HTML},
        required_facts=("application/pdf", "pages", "bytes_hint"),
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
