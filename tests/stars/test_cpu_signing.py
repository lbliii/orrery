"""P0 regression coverage for durable CPU Star Envelope identities."""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from public_keys import public_key_set
from stars.cpu_signing import CPU_KEY_ID_ENV, CPU_PRIVATE_KEY_ENV
from stars.csv_report.skill import build_skill as build_csv
from stars.image_transform.skill import build_skill as build_image


class _Service:
    def result(self, run_id: str) -> dict[str, object]:
        return {"run_id": run_id, "state": "succeeded", "receipt": {"sha256": "sha256:ok"}}


def test_fresh_cpu_factories_share_configured_key_and_jwk_verifies_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = Ed25519PrivateKey.generate()
    monkeypatch.setenv(CPU_PRIVATE_KEY_ENV, private.private_bytes_raw().hex())
    monkeypatch.setenv(CPU_KEY_ID_ENV, "cpu-2026-08")
    csv, image = build_csv(service=_Service()), build_image(service=_Service())
    key_set = public_key_set(
        {"orrery/csv-report": csv, "orrery/image-transform": image}, origin="https://orrery.lol"
    )
    assert {entry["kid"] for entry in key_set["keys"]} == {"cpu-2026-08"}
    for skill in (csv, image):
        envelope = next(item for item in skill._pending if item.name == "result").handler(
            run_id="run-1"
        )
        wire = envelope.to_wire()
        entry = next(item for item in key_set["keys"] if item["kid"] == wire["key_id"])
        encoded = str(entry["x"])
        public = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
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
        message = json.dumps(
            fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        Ed25519PublicKey.from_public_bytes(public).verify(
            base64.b64decode(wire["signature"]), message
        )
        assert wire["key_id"] == "cpu-2026-08"


@pytest.mark.parametrize("value", [None, "not-hex", "00"])
def test_production_cpu_key_is_required_and_valid(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    monkeypatch.setenv("CHIRP_ENV", "production")
    if value is None:
        monkeypatch.delenv(CPU_PRIVATE_KEY_ENV, raising=False)
        with pytest.raises(RuntimeError, match="ORRERY_CPU_PRIVATE_KEY"):
            build_csv(service=_Service())
    else:
        monkeypatch.setenv(CPU_PRIVATE_KEY_ENV, value)
        with pytest.raises(ValueError, match="ORRERY_CPU_PRIVATE_KEY"):
            build_image(service=_Service())
