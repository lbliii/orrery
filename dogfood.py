"""Temporary dogfood skills for the Orrery host — N wrapped ``chirp.skill`` apps.

Gaze / Resolve / html-to-pdf share one aggregated ``/mcp`` with unique tool
names. Gaze discovers skills (``gaze_match`` / ``gaze_search`` /
``gaze_describe`` / ``gaze_list_constellations``); Resolve returns Skill DNS
via ``resolve_name``; html-to-pdf is the Call / Envelope demo star (issues
#25-#27): stub conversion, real Chirp Envelope signing.

Each skill has a golden corpus entry that passes the publish oracle
(``run_publish_gate`` / smoke harness).
"""

from __future__ import annotations

import os
from typing import Any

from chirp.skill import Envelope, Skill, verify_envelope
from chirp.skill.smoke import CorpusPrompt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog import CATALOG

#: How many dogfood skills this host mounts (Foundation epic #2).
N_DOGFOOD_SKILLS = 3

#: Smoke HTML used by the star detail receipt and corpus.
SMOKE_HTML = "<!doctype html><html><body><h1>Orrery</h1></body></html>"

_html_to_pdf_skill: Skill | None = None


def _load_or_generate_key(env_name: str) -> Ed25519PrivateKey:
    raw = os.environ.get(env_name, "").strip()
    if raw:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
    return Ed25519PrivateKey.generate()


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


def get_html_to_pdf_skill() -> Skill:
    """Return the shared html-to-pdf skill (same instance the host mounts)."""
    global _html_to_pdf_skill
    if _html_to_pdf_skill is None:
        _html_to_pdf_skill = build_html_to_pdf_skill()
    return _html_to_pdf_skill


def _tool_handler(skill: Skill, name: str) -> Any:
    for pending in skill._pending:
        if pending.name == name:
            return pending.handler
    msg = f"Skill {skill.name!r} has no tool {name!r}"
    raise KeyError(msg)


def signed_convert_receipt(
    html: str = SMOKE_HTML,
    *,
    skill: Skill | None = None,
) -> tuple[dict[str, Any], bool]:
    """Invoke ``convert`` and return ``(receipt_dict, verified)``.

    Receipt includes Chirp Envelope wire fields plus a stub ``payment_id`` for
    star-page mock parity (commerce lands later).
    """
    sk = skill or get_html_to_pdf_skill()
    envelope: Envelope = _tool_handler(sk, "convert")(html=html)
    verified = verify_envelope(envelope, sk.public_key)
    receipt = envelope.to_wire()
    receipt["payment_id"] = "pay_smoke"
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


def verify_receipt(
    data: dict[str, Any],
    *,
    skill: Skill | None = None,
) -> bool:
    """Verify a receipt dict against the html-to-pdf public key (fails closed)."""
    sk = skill or get_html_to_pdf_skill()
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
)
