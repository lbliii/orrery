"""Load a fresh Orrery App for each test."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Deterministic UTC fixture so world-time smoke/MCP tests need no network.
_WORLD_TIME_FIXTURE = {
    "dateTime": "2026-08-08T12:00:00",
    "date": "08/08/2026",
    "time": "12:00",
    "timeZone": "UTC",
    "dayOfWeek": "Saturday",
}


@pytest.fixture
def example_app(monkeypatch: pytest.MonkeyPatch):
    """Re-exec ``app.py`` with publish-oracle skipped (async-safe)."""
    monkeypatch.setenv("ORRERY_SKIP_PUBLISH", "1")
    monkeypatch.setenv("CHIRP_ENV", "development")
    monkeypatch.setenv("CHIRP_DEBUG", "1")
    monkeypatch.setenv("CHIRP_SECRET_KEY", "test-secret-not-for-production")
    monkeypatch.setenv("ORRERY_WORLD_TIME_JSON", json.dumps(_WORLD_TIME_FIXTURE))

    module_name = "orrery_app_under_test"
    app_path = ROOT / "app.py"

    # Drop prior load so each test gets clean mount state.
    for name in list(sys.modules):
        if name in {module_name, "dogfood"} or name.startswith("orrery_app_"):
            sys.modules.pop(name, None)

    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        yield module.app
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(ROOT))
        sys.modules.pop(module_name, None)
        sys.modules.pop("dogfood", None)
