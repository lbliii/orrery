"""Rolling counters for public sky vitals (#408, persistence #410)."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from chirp.tools.events import ToolCallEvent, ToolEventBus

from namespaces import list_namespaces
from sky.storage import SkyVitalsStorage, storage_from_env
from stars.builtins import builtin_registry

_HOUR_SECONDS = 3600.0
_DAY_SECONDS = 86400.0
_WEEK_SECONDS = 7 * _DAY_SECONDS


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _catalog_counts() -> tuple[int, int]:
    definitions = tuple(builtin_registry())
    stars_live = sum(definition.kind == "star" for definition in definitions)
    constellations_live = sum(
        definition.kind == "constellation" for definition in definitions
    )
    return stars_live, constellations_live


class SkyVitalsStore:
    """Rolling host-truth counters for invocations, resolves, and seals."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        storage: SkyVitalsStorage | None = None,
    ) -> None:
        self._clock = clock or time.time
        self._lock = threading.Lock()
        self._storage = storage if storage is not None else storage_from_env()
        self._invocations: deque[float] = deque()
        self._resolves: deque[float] = deque()
        self._seals: deque[float] = deque()
        self._resolved_names: deque[tuple[str, float]] = deque()
        self._last_invocation_at: float | None = None
        self._restore_from_storage()

    def _restore_from_storage(self) -> None:
        data = self._storage.load()
        if not data:
            return
        with self._lock:
            self._invocations = deque(float(ts) for ts in data.get("invocations", []))
            self._resolves = deque(float(ts) for ts in data.get("resolves", []))
            self._seals = deque(float(ts) for ts in data.get("seals", []))
            self._last_invocation_at = data.get("last_invocation_at")
            self._resolved_names = deque(
                (entry["name"], float(entry["ts"]))
                for entry in data.get("resolved_names", [])
                if isinstance(entry, dict) and "name" in entry and "ts" in entry
            )
            self._prune_locked(self._clock())

    def record_invocation(
        self,
        tool_name: str,
        *,
        arguments: dict[str, Any] | None = None,
        timestamp: float | None = None,
    ) -> None:
        ts = self._clock() if timestamp is None else timestamp
        with self._lock:
            self._invocations.append(ts)
            self._last_invocation_at = ts
            if tool_name == "resolve_name":
                self._resolves.append(ts)
                name = (arguments or {}).get("name")
                if isinstance(name, str) and name.strip():
                    self._resolved_names.append((name.strip(), ts))
            self._prune_locked(self._clock())
            self._persist_locked()

    def record_tool_event(self, event: ToolCallEvent) -> None:
        self.record_invocation(
            event.tool_name,
            arguments=event.arguments,
            timestamp=event.timestamp,
        )

    def record_seal(self, *, timestamp: float | None = None) -> None:
        ts = self._clock() if timestamp is None else timestamp
        with self._lock:
            self._seals.append(ts)
            self._prune_locked(self._clock())
            self._persist_locked()

    def _prune_locked(self, now: float) -> None:
        day_cutoff = now - _DAY_SECONDS
        week_cutoff = now - _WEEK_SECONDS
        self._invocations = deque(ts for ts in self._invocations if ts >= day_cutoff)
        self._resolves = deque(ts for ts in self._resolves if ts >= day_cutoff)
        self._seals = deque(ts for ts in self._seals if ts >= day_cutoff)
        self._resolved_names = deque(
            (name, ts) for name, ts in self._resolved_names if ts >= week_cutoff
        )

    def _top_resolved_7d_locked(self, now: float) -> list[dict[str, Any]]:
        week_cutoff = now - _WEEK_SECONDS
        counts: dict[str, int] = {}
        for name, ts in self._resolved_names:
            if ts >= week_cutoff:
                counts[name] = counts.get(name, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        return [{"name": name, "resolves": count} for name, count in ranked]

    def _persist_locked(self) -> None:
        self._storage.save(
            {
                "invocations": list(self._invocations),
                "resolves": list(self._resolves),
                "seals": list(self._seals),
                "last_invocation_at": self._last_invocation_at,
                "resolved_names": [
                    {"name": name, "ts": ts} for name, ts in self._resolved_names
                ],
            }
        )

    def snapshot(self) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            self._prune_locked(now)
            invocations = list(self._invocations)
            resolves = list(self._resolves)
            seals = list(self._seals)
            last_at = self._last_invocation_at
            top_resolved_7d = self._top_resolved_7d_locked(now)

        stars_live, constellations_live = _catalog_counts()
        activity: dict[str, Any] = {
            "invocations_1h": sum(1 for ts in invocations if ts >= now - _HOUR_SECONDS),
            "invocations_24h": len(invocations),
            "resolves_24h": len(resolves),
            "seals_24h": len(seals),
            "last_invocation_at": _iso_utc(last_at) if last_at is not None else None,
        }
        if top_resolved_7d:
            activity["top_resolved_7d"] = top_resolved_7d
        return {
            "generated_at": _iso_utc(now),
            "catalog": {
                "stars_live": stars_live,
                "constellations_live": constellations_live,
            },
            "activity": activity,
            "demand": {
                "useful_7d": 0,
            },
            "tenancy": {
                "namespaces_live": len(list_namespaces()),
            },
        }


class VitalsRecordingToolEventBus(ToolEventBus):
    """``ToolEventBus`` that records each emission on a ``SkyVitalsStore``."""

    __slots__ = ("_vitals_store",)

    def __init__(self, store: SkyVitalsStore) -> None:
        super().__init__()
        self._vitals_store = store

    async def emit(self, event: ToolCallEvent) -> None:
        self._vitals_store.record_tool_event(event)
        await super().emit(event)


def attach_vitals_to_tool_events(app: Any, store: SkyVitalsStore) -> None:
    """Wire ``tool_events`` to record invocations on *store*."""
    app._mutable_state.tool_events = VitalsRecordingToolEventBus(store)
