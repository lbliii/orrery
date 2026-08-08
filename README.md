# Orrery

**Skills you point at, not install.**

Gaze to discover, resolve to lock the record, call for a verified result — from any machine, any harness.

Catalogs hand you a repo. Orrery hands you an endpoint, a digest, and a receipt — so the agent can keep moving.

## Flow

1. **Gaze** — discover skills across the public sky or a private namespace
2. **Resolve** — name → MCP URL, public key, content digest, price
3. **Call** — invoke with a sealed envelope / receipt

Addresses look like skill DNS:

```
mcp://orrery.dev/gaze              # public sky
mcp://acme.orrery.dev/gaze         # private namespace
mcp://acme.orrery.dev/constellations/docs-gate
```

## Status

Early product repo. Design direction is validated in [`design/`](./design/) (HTML/CSS mocks). Implementation is next.

**Frozen favorite:** [`design/v1-night-gold/`](./design/v1-night-gold/) — night observatory / brass on deep space.

## Preview the mocks

```bash
cd design
python -m http.server 8765
# open http://localhost:8765
```

## Screens

| File | Screen |
|---|---|
| [design/index.html](./design/index.html) | Landing |
| [design/gaze.html](./design/gaze.html) | MCP gaze nodes |
| [design/resolve.html](./design/resolve.html) | Skill DNS |
| [design/star.html](./design/star.html) | Star + Envelope seal |
| [design/constellation.html](./design/constellation.html) | Policy graph |
| [design/namespace.html](./design/namespace.html) | Private namespace |

## License

TBD.
