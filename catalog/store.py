"""In-memory resolve catalog — the ``resolve(name)`` lookup.

``Catalog`` is a thin, deterministic index over :class:`ResolveRecord` seeds.
It is the server-side half of the resolver mock's client behavior in
``design/motion.js`` (match by full name, namespaced name, or bare name).
Gaze discovery (``match`` / ``search`` / ``describe`` / ``list_constellations``)
reads the same index — one seed list, two product surfaces.
"""

from __future__ import annotations

from .dns import mcp_url
from .fixtures import CONSTELLATION_SEEDS
from .gaze import (
    GAZE_NODE_TOOLS,
    GazeHit,
    GazeNode,
    _tokens,
    clamp_gaze_limit,
    hit_from_record,
    is_reactive_record,
    records_for_gaze_node,
    score_record,
    tool_hit,
)
from .models import ResolveRecord


class Catalog:
    """A resolvable index of skill records keyed by name."""

    def __init__(self, records: tuple[ResolveRecord, ...] = CONSTELLATION_SEEDS) -> None:
        self._records = records
        self._by_name = {r.name: r for r in records}

    def reload(self, records: tuple[ResolveRecord, ...]) -> None:
        """Replace index contents in place (keeps importers on the same instance)."""
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

    # ------------------------------------------------------------------
    # Gaze discovery (issues #22 / #23)
    # ------------------------------------------------------------------

    def records_for_node(self, node: str | None = None) -> tuple[ResolveRecord, ...]:
        """Records visible under a gaze node id (``public`` / namespace / …)."""
        return records_for_gaze_node(self._records, node)

    def match(
        self,
        intent: str,
        *,
        node: str = "public",
        limit: int | None = None,
    ) -> tuple[GazeHit, ...]:
        """Rank catalog records for an agent intent (bounded shortlist)."""
        cap = clamp_gaze_limit(limit)
        tokens = _tokens(intent)
        scored: list[tuple[int, ResolveRecord]] = []
        for record in self.records_for_node(node):
            score = score_record(record, tokens)
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return tuple(hit_from_record(record) for _, record in scored[:cap])

    def search(
        self,
        query: str,
        *,
        node: str | None = None,
        limit: int | None = None,
    ) -> tuple[GazeHit, ...]:
        """Substring search over name + description + agent card text."""
        cap = clamp_gaze_limit(limit)
        q = (query or "").strip().lower()
        pool = self.records_for_node(node)
        if not q:
            return tuple(hit_from_record(r) for r in pool[:cap])

        def _matches(record: ResolveRecord) -> bool:
            if q in record.name.lower():
                return True
            if q in (record.resolved_description() or "").lower():
                return True
            card = record.agent_card
            return card is not None and q in card.searchable_text()

        hits = [hit_from_record(r) for r in pool if _matches(r)]
        return tuple(hits[:cap])

    def describe(self, name: str) -> dict[str, object]:
        """Richer manifest-ish metadata without executing tools."""
        record = self.resolve(name)
        if record is None:
            return {"error": "not_found", "name": name, "status": "not_found"}
        payload: dict[str, object] = {
            "name": record.name,
            "version": record.version,
            "kind": record.kind,
            "visibility": record.visibility,
            "description": record.resolved_description(),
            "endpoint": record.endpoint,
            "content_digest": record.content_digest,
            "key_id": record.key_id,
            "price_per_call": record.price_per_call,
            "oracle_ok": record.oracle_ok,
            "tools": list(record.tools),
            "href": record.href,
            "provider_card": record.provider_card.as_dict() if record.provider_card else None,
            "agent_card": record.agent_card.as_dict() if record.agent_card else None,
            "status": "ok",
        }
        if record.kind == "constellation":
            from .constellation import policy_for

            graph = policy_for(record.name)
            if graph is not None:
                payload["policy_digest"] = record.content_digest
                payload["policy_nodes"] = [n.id for n in graph.nodes]
                payload["policy_edges"] = [
                    {"source": e.source, "target": e.target, "kind": e.kind} for e in graph.edges
                ]
            card = record.agent_card
            if card is not None:
                if card.run_contract is not None:
                    payload["run_contract"] = dict(card.run_contract)
                if card.graph_summary is not None:
                    payload["graph_summary"] = card.graph_summary
                if card.dispositions is not None:
                    payload["dispositions"] = list(card.dispositions)
                if card.member_stars is not None:
                    payload["member_stars"] = [dict(item) for item in card.member_stars]
        return payload

    def list_constellations(self, *, node: str | None = None) -> tuple[GazeHit, ...]:
        """Constellation-kind records (optionally scoped to a gaze node)."""
        pool = self.records_for_node(node)
        return tuple(hit_from_record(r) for r in pool if r.kind == "constellation")

    def gaze_nodes(self) -> tuple[GazeNode, ...]:
        """Console node tabs: public sky, namespace, then a constellation node."""
        namespaces = sorted(
            {r.namespace for r in self._records if r.namespace and r.visibility == "private"}
        )
        nodes: list[GazeNode] = [
            GazeNode(
                id="public",
                label="Public sky",
                url=mcp_url("/gaze"),
                scope="orrery/*",
                tools=GAZE_NODE_TOOLS,
            )
        ]
        for ns in namespaces:
            nodes.append(
                GazeNode(
                    id=ns,
                    label=f"{ns} namespace",
                    url=mcp_url("/gaze", namespace=ns),
                    scope=f"{ns}/*",
                    tools=GAZE_NODE_TOOLS,
                )
            )
        # Constellation node: first constellation's tools (progressive disclosure).
        constellation = next(
            (r for r in self._records if r.kind == "constellation"),
            None,
        )
        if constellation is not None:
            nodes.append(
                GazeNode(
                    id="docs",
                    label=f"{constellation.short_name} node",
                    url=constellation.endpoint,
                    scope="constellation",
                    tools=constellation.tools or ("run", "status"),
                )
            )
        return tuple(nodes)

    def hits_for_node(
        self,
        node_id: str,
        *,
        intent: str = "",
        limit: int | None = None,
    ) -> tuple[GazeHit, ...]:
        """Hits shown for a console node (records or constellation tools)."""
        key = (node_id or "public").strip().lower()
        if key == "docs":
            constellation = next(
                (r for r in self._records if r.kind == "constellation"),
                None,
            )
            if constellation is None:
                return ()
            tools = constellation.tools or ("run", "status")
            return tuple(tool_hit(t, constellation=constellation) for t in tools)
        if intent.strip():
            return self.match(intent, node=key, limit=limit)
        cap = clamp_gaze_limit(limit)
        records = self.records_for_node(key)
        ordered = tuple(
            sorted(records, key=lambda record: (not is_reactive_record(record), record.name))
        )
        return tuple(hit_from_record(r) for r in ordered[:cap])


#: Process-wide catalog; refreshed from live manifests after publish-oracle.
CATALOG = Catalog()


def replace_catalog(records: tuple[ResolveRecord, ...]) -> Catalog:
    """Refresh the process-wide catalog after publish-oracle manifest sync."""
    CATALOG.reload(records)
    return CATALOG
