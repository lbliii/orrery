# Verify an Orrery Envelope without calling Orrery again

Resolve the Star, fetch its `public_key_url`, find the key whose `kid` equals
the Envelope `key_id`, and verify locally. Orrery publishes a JWKS-like key
set at `/.well-known/orrery/keys.json`. Key entries are `OKP` / `Ed25519`;
their JWK `alg` is `EdDSA`, while the Envelope wire field remains `Ed25519`.

Cache the key set using its HTTP `Cache-Control` value. On an unknown `kid`,
refresh once before failing. Rotation publishes a new key before it is used and
retains old keys through the relevant verification window; clients must bind
the key lookup to the Envelope `key_id`, never just use the newest key.

The signed UTF-8 message is canonical JSON of exactly these fields, with
lexicographic key sort, separators `,` and `:`, and no `signature` field:
`payload`, `skill`, `version`, `tool`, `nonce`, `input_digest`, `key_id`, and
`alg`. JSON values use their ordinary JSON representation (UTF-8, not ASCII
escaping). Reject a wire `alg` other than `Ed25519`.

```python
import base64, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def verify(envelope: dict, key_set: dict) -> None:
    assert envelope["alg"] == "Ed25519"
    key = next(item for item in key_set["keys"] if item["kid"] == envelope["key_id"])
    raw_key = base64.urlsafe_b64decode(key["x"] + "=" * (-len(key["x"]) % 4))
    fields = {name: envelope[name] for name in (
        "payload", "skill", "version", "tool", "nonce", "input_digest", "key_id", "alg"
    )}
    message = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    Ed25519PublicKey.from_public_bytes(raw_key).verify(base64.b64decode(envelope["signature"]), message)
```

In JavaScript, construct the same fields object, serialize it with a canonical
JSON implementation that sorts keys recursively, and verify with an Ed25519
WebCrypto implementation after base64url-decoding JWK `x`. Native
`JSON.stringify` alone is not sufficient because it preserves insertion order
rather than supplying the required canonical key sort.

Artifact verification is separate: after Envelope verification, download the
artifact, calculate SHA-256 over the exact bytes, and compare it with the
receipt payload's `sha256` value. A valid signature does not replace the
digest check.
