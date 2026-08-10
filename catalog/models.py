"""Resolve record schema — Orrery's "Skill DNS".

A :class:`ResolveRecord` is what a ``resolve(name)`` call returns: the live
coordinates an agent needs to *call* a skill without cloning or installing it.
This mirrors the resolver console mock (``design/resolve.html``) and the star
detail mock (``design/star.html``) and backs GitHub epic #4 (Resolve).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .provider import ProviderCard

#: A public star, or a private/constellation entry.
Kind = str  # "star" | "constellation"
Visibility = str  # "public" | "private"


@dataclass(frozen=True, slots=True)
class ResolveRecord:
    """One resolvable name → the record an agent calls against.

    Fields map to the resolve JSON contract shown in the mocks::

        GET /resolve?name=orrery/html-to-pdf
        → endpoint, key_id, content_digest, price_per_call, alg
    """

    name: str
    endpoint: str
    content_digest: str
    kind: Kind = "star"
    visibility: Visibility = "public"
    version: str | None = None
    description: str = ""
    key_id: str | None = None
    alg: str = "Ed25519"
    price_per_call: str | None = None
    oracle_ok: bool = True
    tools: tuple[str, ...] = field(default_factory=tuple)
    provider_card: ProviderCard | None = None
    capability_families: tuple[str, ...] = field(default_factory=tuple)
    freshness: str | None = None
    constellation_memberships: tuple[str, ...] = field(default_factory=tuple)

    @property
    def short_name(self) -> str:
        """Name without the namespace prefix (``orrery/html-to-pdf`` → ``html-to-pdf``)."""
        return self.name.split("/", 1)[-1]

    @property
    def namespace(self) -> str | None:
        """Namespace prefix, or ``None`` for unqualified names."""
        return self.name.split("/", 1)[0] if "/" in self.name else None

    @property
    def href(self) -> str:
        """Detail-page path for this record (star vs constellation)."""
        if self.kind == "star" and self.namespace:
            return f"/star/{self.namespace}/{self.short_name}"
        base = "/constellations" if self.kind == "constellation" else "/stars"
        return f"{base}?name={self.name}"

    @property
    def is_paid(self) -> bool:
        return bool(self.price_per_call)

    @property
    def is_free(self) -> bool:
        return not self.is_paid

    @property
    def pricing_label(self) -> str:
        """Human-facing toll label for UI and gaze blurbs."""
        return self.price_per_call if self.is_paid else "Free"

    @property
    def tools_display(self) -> str:
        """Comma-joined tool list for templates."""
        return ", ".join(self.tools)

    @property
    def primary_tool(self) -> str:
        """First tool name, or a generic ``call`` fallback."""
        return self.tools[0] if self.tools else "call"

    def as_dict(self) -> dict[str, object]:
        """Serialize to the ``/api/resolve`` JSON contract."""
        return {
            "name": self.name,
            "version": self.version,
            "kind": self.kind,
            "visibility": self.visibility,
            "endpoint": self.endpoint,
            "key_id": self.key_id,
            "alg": self.alg,
            "content_digest": self.content_digest,
            "price_per_call": self.price_per_call,
            "oracle_ok": self.oracle_ok,
            "tools": list(self.tools),
            "provider_card": self.provider_card.as_dict() if self.provider_card else None,
            "capability_families": list(self.capability_families),
            "freshness": self.freshness,
            "constellation_memberships": list(self.constellation_memberships),
        }
