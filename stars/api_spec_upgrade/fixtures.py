"""Re-export API-spec migration star fixtures for constellation acceptance (#179)."""

from __future__ import annotations

from stars.api_spec_openapi_upgrade_safe.fixtures import (
    EXTENSION_SPEC,
    MALFORMED_SPEC,
    SAFE_SPEC,
    UNSUPPORTED_SPEC,
)

__all__ = ["EXTENSION_SPEC", "MALFORMED_SPEC", "SAFE_SPEC", "UNSUPPORTED_SPEC"]
