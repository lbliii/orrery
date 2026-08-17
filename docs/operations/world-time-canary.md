# World-time public canary

Run the independent public check with:

```bash
uv run python scripts/canary_world_time.py --origin https://orrery.lol
```

It calls the public direct MCP endpoint (`/stars/world-time/mcp`), fetches the public
JWK set (`/.well-known/orrery/keys.json`), parses ADR 0010 JSON
(`envelope_wire`, not a Python `Envelope(...)` repr), selects the key
explicitly published for `orrery/world-time`, verifies the Ed25519
signature, and checks that the live UTC observation is no more than 15 minutes old.
It does not use Orrery credentials, Redis, the worker, or a private signing key.

The GitHub Actions workflow runs on a daily schedule and can be dispatched manually.
It is deliberately non-blocking (`continue-on-error: true`): a clock-provider or
network outage is visible in the workflow but does not gate pull requests or releases.
When it fails, rerun once to distinguish a transient upstream failure from an Orrery
regression; investigate repeated failures, signature/key mismatches, malformed MCP
responses, or stale observations as production incidents.
