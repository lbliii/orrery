# Cross-namespace public star references

Private-namespace constellations (for example `acme/*`) may reference **public**
stars (`orrery/*`) in their policy graphs. Resolve still returns publisher
coordinates only; the agent calls each star MCP endpoint directly ([ADR
0004](../adr/0004-publisher-direct-call.md)). Gaze and describe surfaces state
this rule — they do not invent a router or proxy execution path ([ADR
0005](../adr/0005-discovery-and-dual-trust.md)).

## Rule

1. **Constellation locality stays private** — the composite node lives under the
   tenant namespace (`acme/launch-gate`, not a public-sky entry).
2. **Member stars may span namespaces** — graph nodes may cite public stars by
   full name (`orrery/html-to-pdf`). Agents resolve each ref and call the
   publisher endpoint on the returned card.
3. **No fake private sky** — this leaf documents and dogfoods the pattern only.
   Full namespace tenancy, provisioning, and gaze scoping remain tracked in
   #28 / #29 / #70.

## Dogfood example

`acme/launch-gate` is the demo private constellation. Its policy graph mixes
`acme/secret-scan`, `acme/license-check`, and `acme/human-approve` with the
public star `orrery/html-to-pdf` (marked `*` in the viewer footnote).

Inspect via agent card / gaze describe:

```python
from catalog import CATALOG

described = CATALOG.describe("acme/launch-gate")
card = described["agent_card"]
assert any("public" in bullet.lower() for bullet in card["use_when"])
```

Member stars on the card list both namespace prefixes — public refs are
expected, not errors.

## What this does not cover

- Namespace provisioning or ACL enforcement (#28, #29)
- Gaze ranking / match scoping for private tenants (#70)
- Changing resolve to execute tools on behalf of callers
