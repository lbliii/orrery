"""Temporary dogfood skills for the Orrery host — N wrapped ``chirp.skill`` apps.

Gaze / Resolve / Star share one aggregated ``/mcp`` with unique tool names.
Gaze discovers skills (``gaze_match`` / ``gaze_search`` / ``gaze_describe`` /
``gaze_list_constellations``); Resolve returns Skill DNS via ``resolve_name``;
Star remains a seal stub until the Call epic lands.

Each skill has a golden corpus entry that passes the publish oracle
(``run_publish_gate`` / smoke harness).
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from chirp.skill import Skill
from chirp.skill.smoke import CorpusPrompt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog import CATALOG

#: How many dogfood skills this host mounts (Foundation epic #2).
N_DOGFOOD_SKILLS = 3


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


def build_star_skill(*, private_key: Any | None = None) -> Skill:
    """Star — seal a short label into a deterministic digest hint."""
    private = private_key or _load_or_generate_key("ORRERY_STAR_PRIVATE_KEY")
    public = private.public_key().public_bytes_raw()
    skill = Skill(
        "star",
        version="1.0.0",
        private_key=private,
        key_id=os.environ.get("ORRERY_STAR_KEY_ID", "star-1"),
        public_key=public,
    )

    @skill.tool("seal_label", description="Seal a label into a digest hint")
    def seal_label(label: str) -> dict[str, str]:
        digest = "sha256:" + hashlib.sha256(label.encode()).hexdigest()[:16]
        return {"label": label, "sealed": "true", "digest": digest}

    return skill


def build_dogfood_skills() -> tuple[Skill, ...]:
    """Return the N dogfood skills in mount order."""
    skills = (
        build_gaze_skill(),
        build_resolve_skill(),
        build_star_skill(),
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
        id="star-seal-orion",
        prompt="Seal the label Orion.",
        tool="seal_label",
        arguments={"label": "Orion"},
        required_facts=("Orion", "sealed", "sha256:"),
    ),
)
