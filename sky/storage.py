"""Env-gated persistence for ``SkyVitalsStore`` (#410)."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable

KEY_PREFIX = "orrery:sky-vitals:"
STATE_KEY = f"{KEY_PREFIX}state"


@runtime_checkable
class SkyVitalsStorage(Protocol):
    """Load/save serialized vitals counters."""

    def load(self) -> dict[str, Any] | None: ...

    def save(self, state: dict[str, Any]) -> None: ...


class NoOpStorage:
    """In-process only — no cross-process persistence."""

    def load(self) -> dict[str, Any] | None:
        return None

    def save(self, state: dict[str, Any]) -> None:
        del state


class RedisStorage:
    """Persist vitals state in Redis when ``REDIS_URL`` is configured."""

    def __init__(self, redis_client: Any, *, key: str = STATE_KEY) -> None:
        self._redis = redis_client
        self._key = key

    def load(self) -> dict[str, Any] | None:
        raw = self._redis.get(self._key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return json.loads(raw)

    def save(self, state: dict[str, Any]) -> None:
        self._redis.set(self._key, json.dumps(state))


def storage_from_env(*, redis_client: Any | None = None) -> SkyVitalsStorage:
    """Return Redis-backed storage when ``REDIS_URL`` is set, else no-op."""
    if redis_client is not None:
        return RedisStorage(redis_client)
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return NoOpStorage()
    import redis

    return RedisStorage(redis.Redis.from_url(url))
