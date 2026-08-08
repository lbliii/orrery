"""In-memory resolve catalog — the ``resolve(name)`` lookup.

``Catalog`` is a thin, deterministic index over :class:`ResolveRecord` seeds.
It is the server-side half of the resolver mock's client behavior in
``design/motion.js`` (match by full name, namespaced name, or bare name).
Later epics swap the seed list for the live skill registry; the ``resolve``
contract stays the same.
"""

from __future__ import annotations

from .fixtures import SEED_RECORDS
from .models import ResolveRecord


class Catalog:
    """A resolvable index of skill records keyed by name."""

    def __init__(self, records: tuple[ResolveRecord, ...] = SEED_RECORDS) -> None:
        self._records = records
        self._by_name = {r.name: r for r in records}

    def all(self) -> tuple[ResolveRecord, ...]:
        return self._records

    def public_records(self) -> tuple[ResolveRecord, ...]:
        """Records visible in the public resolver zone (mirrors resolve.html)."""
        return tuple(r for r in self._records if r.visibility == "public") + tuple(
            r for r in self._records if r.visibility == "private" and r.kind == "constellation"
        )

    def get(self, name: str) -> ResolveRecord | None:
        return self._by_name.get(name)

    def resolve(self, query: str) -> ResolveRecord | None:
        """Resolve a lookup string to one record.

        Accepts ``name``, ``namespace/name``, or ``name@version`` and matches
        the way the mock resolver does: exact name first, then bare short name,
        then a substring fallback.
        """
        q = (query or "").strip().lower()
        if not q:
            return None
        q = q.split("@", 1)[0]  # drop @version pin

        # 1) exact full-name match
        for record in self._records:
            if record.name.lower() == q:
                return record

        # 2) bare short-name match (html-to-pdf → orrery/html-to-pdf)
        bare = q.split("/", 1)[-1]
        for record in self._records:
            if record.short_name.lower() == bare:
                return record

        # 3) substring fallback (ordered)
        for record in self._records:
            if bare in record.name.lower():
                return record
        return None


#: Process-wide catalog seeded from the design mocks.
CATALOG = Catalog()
