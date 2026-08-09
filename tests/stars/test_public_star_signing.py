from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from public_keys import public_key_set
from stars.csv_url.skill import build_skill as build_csv
from stars.html_to_pdf.skill import build_skill as build_pdf
from stars.http_head.skill import build_skill as build_head
from stars.source_watch.skill import build_skill as build_watch
from stars.spdx_license.skill import build_skill as build_spdx
from stars.well_known.skill import build_skill as build_well_known
from stars.world_time.skill import build_skill as build_time


def _verify(wire: dict[str, object], jwk: dict[str, object]) -> None:
    fields = {
        name: wire[name]
        for name in (
            "payload",
            "skill",
            "version",
            "tool",
            "nonce",
            "input_digest",
            "key_id",
            "alg",
        )
    }
    message = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    encoded = str(jwk["x"])
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    Ed25519PublicKey.from_public_bytes(raw).verify(
        base64.b64decode(str(wire["signature"])), message
    )


def test_global_public_star_key_is_stable_and_verifies_all_factory_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", private.private_bytes_raw().hex())
    monkeypatch.setenv("ORRERY_STAR_KEY_ID", "stars-2026-08")
    monkeypatch.setenv("ORRERY_SOURCE_WATCH_FIXTURES", '{"python-release-notes":"fixture"}')
    import stars.csv_url.skill as csv_module
    import stars.http_head.skill as head_module
    import stars.spdx_license.skill as spdx_module

    csv_module.get_dataset = lambda _dataset: {"dataset": "flights-airport"}
    head_module.observe_head = lambda _target: {"status": 200}
    spdx_module.get_license = lambda _license_id: {"license_id": "MIT"}
    factories = {
        "orrery/html-to-pdf": (build_pdf, "health", {}),
        "orrery/world-time": (build_time, "fetch", {}),
        "orrery/source-watch": (build_watch, "observe", {}),
        "orrery/http-head": (build_head, "head", {}),
        "orrery/well-known": (build_well_known, "read", {}),
        "orrery/spdx-license": (build_spdx, "get", {}),
        "orrery/csv-url": (build_csv, "get", {}),
    }
    first = {name: factory() for name, (factory, _, _) in factories.items()}
    second = {name: factory() for name, (factory, _, _) in factories.items()}
    assert {skill.key_id for skill in first.values()} == {"stars-2026-08"}
    assert {skill.public_key for skill in first.values()} == {
        private.public_key().public_bytes_raw()
    }
    assert {skill.public_key for skill in second.values()} == {
        private.public_key().public_bytes_raw()
    }
    keys = public_key_set(first, origin="https://orrery.lol")["keys"]
    jwk = next(item for item in keys if item["kid"] == "stars-2026-08")
    for skill, (_, tool_name, arguments) in zip(first.values(), factories.values(), strict=True):
        envelope = next(item for item in skill._pending if item.name == tool_name).handler(
            **arguments
        )
        _verify(envelope.to_wire(), jwk)


@pytest.mark.parametrize("key", [None, "bad", "00"])
def test_production_public_stars_fail_without_valid_config(
    monkeypatch: pytest.MonkeyPatch, key: str | None
) -> None:
    monkeypatch.setenv("CHIRP_ENV", "production")
    for name in (
        "ORRERY_STAR_PRIVATE_KEY",
        "ORRERY_PDF_PRIVATE_KEY",
        "ORRERY_WORLD_TIME_PRIVATE_KEY",
        "ORRERY_SOURCE_WATCH_PRIVATE_KEY",
        "ORRERY_HTTP_HEAD_PRIVATE_KEY",
        "ORRERY_WELL_KNOWN_PRIVATE_KEY",
        "ORRERY_SPDX_LICENSE_PRIVATE_KEY",
        "ORRERY_CSV_URL_PRIVATE_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    if key is not None:
        monkeypatch.setenv("ORRERY_STAR_PRIVATE_KEY", key)
    for factory in (
        build_pdf,
        build_time,
        build_watch,
        build_head,
        build_well_known,
        build_spdx,
        build_csv,
    ):
        with pytest.raises((RuntimeError, ValueError)):
            factory()
