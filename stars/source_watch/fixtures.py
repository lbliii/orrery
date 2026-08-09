"""Deterministic Source Watch fixtures for local tests and publish smoke."""

from __future__ import annotations

import json
from typing import Final

from .contract import DEFAULT_SOURCE

RELEASE_NOTES_FIXTURE: Final = "Python 3.14 release notes include security guidance."


def fixture_environment(document: str = RELEASE_NOTES_FIXTURE) -> dict[str, str]:
    """Return the environment mapping consumed by :mod:`.service`."""
    return {"ORRERY_SOURCE_WATCH_FIXTURES": json.dumps({DEFAULT_SOURCE: document})}
