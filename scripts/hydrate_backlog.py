#!/usr/bin/env python3
"""One-shot backlog hydration for lbliii/orrery. Safe to re-run? No — creates issues."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass


REPO = "lbliii/orrery"


def run(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(args)}")
    return result.stdout.strip()


def create_issue(title: str, labels: list[str], body: str) -> int:
    cmd = ["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body]
    for label in labels:
        cmd.extend(["-l", label])
    url = run(cmd)
    number = int(url.rsplit("/", 1)[-1])
    print(f"#{number} {title}")
    return number


def node_id(number: int) -> str:
    data = run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={{repository(owner:\"lbliii\",name:\"orrery\"){{issue(number:{number}){{id}}}}}}",
        ]
    )
    return json.loads(data)["data"]["repository"]["issue"]["id"]


def add_sub_issue(parent: int, child: int) -> None:
    parent_id = node_id(parent)
    child_id = node_id(child)
    mutation = """
    mutation($parent:ID!, $child:ID!) {
      addSubIssue(input: {issueId: $parent, subIssueId: $child}) {
        issue { number }
      }
    }
    """
    run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={mutation}",
            "-f",
            f"parent={parent_id}",
            "-f",
            f"child={child_id}",
        ]
    )
    print(f"  linked #{child} → parent #{parent}")


@dataclass(frozen=True)
class Issue:
    key: str
    title: str
    labels: tuple[str, ...]
    body: str
    parent_key: str | None = None


ISSUES: list[Issue] = [
    Issue(
        key="saga",
        title="[Saga] Orrery — skills you point at, not install",
        labels=("saga", "P0"),
        body="""## North star

Skills you **point at**, not install. Gaze to discover, resolve to lock the record, call for a verified result — from any machine, any harness.

Catalogs hand you a repo. Orrery hands you an **endpoint**, a **content digest**, and a **signed Envelope** — so the agent can keep moving.

## Provenance

- **Design validated:** [`design/`](./tree/main/design) high-fidelity mocks (night observatory / brass on deep space). Frozen favorite: `design/v1-night-gold/`.
- **Framework saga:** [lbliii/chirp#959](https://github.com/lbliii/chirp/issues/959) — `chirp.skill`, Envelope, publish oracle, MCP Apps.
- **Framework platform epic (CLOSED):** [lbliii/chirp#964](https://github.com/lbliii/chirp/issues/964) — registry + console + Railway dogfood (#980–#985).
- **Dogfood host:** `chirp/examples/standalone/orrery/` — aggregated `/mcp`, `/skills`, `/console`, live feed, 3 stub skills. Host plumbing works; product semantics do not.

## Product flow

```
Gaze → Resolve → Call → Verify
```

1. **Gaze** — `match(intent)` across public sky or private namespace (descriptions + prices only).
2. **Resolve** — Skill DNS: `namespace/name@version` → `endpoint`, `key_id`, `content_digest`, `price_per_call`, `alg`.
3. **Call** — tools on `mcp://…/s/{skill}`; result is a signed **Envelope**.
4. **Verify** — trust / pay only when signature verifies; refund on forge.

Addresses (from mocks):

```
mcp://orrery.dev/gaze
mcp://acme.orrery.dev/gaze
mcp://acme.orrery.dev/constellations/docs-gate
mcp://orrery.dev/s/html-to-pdf
```

## Workstreams (epics)

Tracked as child issues — not a checklist:

1. Foundation — Chirp host, dogfood port, tests, Railway
2. Brand — night observatory design system into the live app
3. Gaze — discovery MCP + console
4. Resolve — Skill DNS HTTP + MCP
5. Call / Envelope — star detail, receipts, verify UX
6. Namespaces — private tenancy wedge
7. Constellations — policy graphs + composite receipts
8. Trust & Commerce — oracle surface, pricing (MVP-light)

## Architectural boundaries

- **Chirp owns** transport (`chirp.tools` / `chirp.skill`), Envelope signing, publish oracle (`check`+`freeze`+smoke), MCP Apps UI resources.
- **Orrery owns** product vocabulary (star / gaze / resolve / constellation / namespace), Skill DNS, registry UX, tenancy, constellation orchestration, brand, deploy.
- Authorship stays Python/Chirp where the oracle adds value; consumption stays any MCP client.

## Not now

Untrusted third-party marketplace + isolate sandbox; scale-to-zero FaaS; BYO-key-per-invocation marketplace; constellation authoring editor (viewer first); full payment rail (schema + stubs first).

## Success signal

An agent points at hosted Orrery, gazes/matches a skill, resolves a digest + key, calls it, and receives a verifiable Envelope — while a human browses the same sky in the branded UI.
""",
    ),
    # --- Epics ---
    Issue(
        key="epic-foundation",
        parent_key="saga",
        title="Epic: Foundation — Chirp host, dogfood, tests, Railway",
        labels=("epic", "P0", "foundation", "ready"),
        body="""**Parent saga:** see saga issue.

**Outcome**
A runnable Chirp app in this repo that ports the proven `chirp/examples/standalone/orrery/` host: `mount_skills`, aggregated `/mcp` + `/skills`, `/console`, live feed, publish-oracle smoke, Railway deploy. Product semantics come later; this epic lands the substrate.

**Evidence**
- Chirp example + closed platform epic [#964](https://github.com/lbliii/chirp/issues/964) / [#985](https://github.com/lbliii/chirp/issues/985).
- Design mocks are not required for this epic beyond keeping `/` from going blank under CSP.

**Exit criteria**
- [ ] Local `/health`, `/mcp`, `/skills`, `/console` work.
- [ ] Pytest green in CI.
- [ ] Railway deploy healthy; MCP curl from README works.
""",
    ),
    Issue(
        key="epic-brand",
        parent_key="saga",
        title="Epic: Brand — night observatory design system",
        labels=("epic", "P1", "brand", "design"),
        body="""**Parent saga:** see saga issue.

**Outcome**
The live app matches the validated night-observatory mocks: cosmos background, brass/phosphor tokens, Bricolage + Source Serif + Plex Mono, glass panels, pills, reduced-motion contract, Envelope seal language.

**Evidence**
- Live mocks: `design/*.html`, `design/styles.css`, `design/motion.js`.
- Frozen favorite: `design/v1-night-gold/`.

**Exit criteria**
- [ ] Shared static CSS/JS extracted from mocks and served by the Chirp app.
- [ ] Landing + chrome visually match mocks on desktop and ≤860px.
- [ ] `prefers-reduced-motion` kills cosmos/seal/meteor animations (parity with mock).
""",
    ),
    Issue(
        key="epic-gaze",
        parent_key="saga",
        title="Epic: Gaze — discovery MCP + public sky console",
        labels=("epic", "P1", "gaze", "design"),
        body="""**Parent saga:** see saga issue.

**Outcome**
Gaze is real discovery: MCP node at `mcp://orrery.dev/gaze` (and later `{tenant}.orrery.dev/gaze`) with tools `search`, `match`, `resolve`, `describe`, `list_constellations`. Human console replaces Alpine static data in `design/gaze.html`. Progressive disclosure: descriptions + prices only — no payloads.

**Evidence**
- `design/gaze.html` node model (`public` / `acme` / `docs-gate`) and `match(intent)` response shape.
- Chirp dogfood `gaze` skill is a **stub** (`look_at`) — replace, do not keep astronomy placeholders.

**Exit criteria**
- [ ] Gaze tools return live catalog data.
- [ ] Gaze UI wired to live API (not hardcoded Alpine hits).
- [ ] Namespace-scoped gaze is designed (may land under Namespaces epic).
""",
    ),
    Issue(
        key="epic-resolve",
        parent_key="saga",
        title="Epic: Resolve — Skill DNS",
        labels=("epic", "P0", "resolve", "design"),
        body="""**Parent saga:** see saga issue.

**Outcome**
Skill DNS: name → locked record. HTTP `GET /resolve?name=` and MCP `resolve` return `endpoint`, `key_id`, `content_digest`, `price_per_call`, `alg`. Console matches `design/resolve.html` (zone table, lookup for `name` / `namespace/name` / `name@version`).

**Evidence**
- Resolve panel + table fields in `design/resolve.html`.
- Chirp dogfood `resolve_name` returns `/console/{slug}` only — insufficient for product.

**Exit criteria**
- [ ] Resolve record schema frozen and documented.
- [ ] HTTP + MCP resolve return identical fields.
- [ ] Resolve UI deep-links to star vs constellation by record type.
""",
    ),
    Issue(
        key="epic-call",
        parent_key="saga",
        title="Epic: Call / Envelope — star detail, receipts, verify",
        labels=("epic", "P1", "call", "trust", "design"),
        body="""**Parent saga:** see saga issue.

**Outcome**
Star pages and MCP star endpoints match `design/star.html`: endpoint, tools, digest, key, oracle pills, price, last Envelope. Calling a tool yields a signed Envelope; UI shows seal + verify status. “Copy MCP URL” and “Enable for my agents” become real actions (enablement can be stub allowlist).

**Evidence**
- Envelope JSON fields in `design/star.html`.
- Chirp `Envelope` already signs at the skill layer — product needs UX + verify surface, not a second crypto stack.

**Exit criteria**
- [ ] Star detail page live from resolve/describe.
- [ ] Last Envelope panel with verify-ok / forge-fail states.
- [ ] At least one real demo star tool (can start as html-to-pdf stub that returns a receipt).
""",
    ),
    Issue(
        key="epic-namespace",
        parent_key="saga",
        title="Epic: Namespaces — private tenancy wedge",
        labels=("epic", "P2", "namespace", "commerce", "design"),
        body="""**Parent saga:** see saga issue.

**Outcome**
Private namespaces (`acme/*`) are the SaaS wedge: tenant subdomain gaze/resolve, scoped stars, allowlisted callers, Envelope retention, seat billing model (schema first). “Create namespace” CTA from `design/namespace.html` becomes a provisioning flow.

**Evidence**
- `design/namespace.html` feature list + `mcp://acme.orrery.dev/…` addressing.
- Public free / namespace paid framing in mocks.

**Exit criteria**
- [ ] Tenant routing model decided and documented.
- [ ] Create-namespace flow provisions a scoped catalog.
- [ ] Private resolve pills appear for namespace-owned records.
""",
    ),
    Issue(
        key="epic-constellation",
        parent_key="saga",
        title="Epic: Constellations — policy graphs + composite receipts",
        labels=("epic", "P2", "constellation", "design"),
        body="""**Parent saga:** see saga issue.

**Outcome**
Constellations are composite skills: policy graph (gates, bounded repair loops, fan-in), MCP node tools `run` / `status` / `explain_policy`, composite Envelope chains. Viewer first (from `design/constellation.html`); authoring editor later.

**Evidence**
- `acme/launch-gate` graph + composite receipt chain in `design/constellation.html`.
- Doc Bundle input shape `{ pages, links, examples }` on docs-gate node.
- No Chirp example coverage — greenfield on top of Envelope primitives.

**Exit criteria**
- [ ] Constellation record type in resolve.
- [ ] Graph viewer from live policy definition.
- [ ] `run` produces a composite receipt chain (even if steps are stubbed).
""",
    ),
    Issue(
        key="epic-trust",
        parent_key="saga",
        title="Epic: Trust & Commerce — oracle surface + pricing stubs",
        labels=("epic", "P2", "trust", "commerce"),
        body="""**Parent saga:** see saga issue.

**Outcome**
Product-facing trust: oracle status (`check · freeze · smoke`) visible on resolve/star; Envelope payment fields (`payment_id`, `price_per_call`) with charge-on-verify / refund-on-forge **stubs**; public-free vs namespace-paid enforcement hooks. Full payment provider integration is later.

**Evidence**
- Oracle pills + pricing copy across mocks.
- Chirp publish oracle already exists in-framework; Orrery surfaces it.

**Exit criteria**
- [ ] Oracle status on resolve records and star pages.
- [ ] Pricing fields on resolve/gaze hits.
- [ ] Documented stub payment/refund hooks (no silent no-ops).
""",
    ),
    # --- Foundation children ---
    Issue(
        key="f1",
        parent_key="epic-foundation",
        title="Scaffold Chirp host app (mount_skills + secure_stack)",
        labels=("P0", "foundation", "ready"),
        body="""**Parent epic:** Foundation

**Outcome**
Port the host recipe from `chirp/examples/standalone/orrery/app.py`: `AppConfig.from_env`, production secret guard, `secure_stack` (CSRF exempt `/mcp`), CSP allowing fonts/inline styles as needed, `mount_skills` + `mount_console`.

**Acceptance**
- [ ] `/health`, `/mcp`, `/skills`, `/console` respond locally.
- [ ] Default secret refused in production env.
""",
    ),
    Issue(
        key="f2",
        parent_key="epic-foundation",
        title="Port dogfood skills + golden corpus (temporary stubs)",
        labels=("P0", "foundation", "ready"),
        body="""**Parent epic:** Foundation

**Outcome**
Port `dogfood.py` pattern (N signed skills + `CorpusPrompt` corpus) so publish-oracle smoke and console reliability scores work on day one. Stub tool bodies are fine until Gaze/Resolve/Call epics replace them.

**Acceptance**
- [ ] Boot `freeze` + smoke populates reliability scores (unless `ORRERY_SKIP_PUBLISH=1`).
- [ ] Console shows dogfood skills.
""",
    ),
    Issue(
        key="f3",
        parent_key="epic-foundation",
        title="Port pytest suite + CI on push",
        labels=("P0", "foundation", "ready"),
        body="""**Parent epic:** Foundation

**Outcome**
Adapt `test_app.py` coverage (home, `/skills`, `/console`, MCP list/call, SSE feed, publish gate) and wire GitHub Actions.

**Acceptance**
- [ ] `pytest` green locally.
- [ ] CI runs on push/PR.
""",
    ),
    Issue(
        key="f4",
        parent_key="epic-foundation",
        title="Railway Dockerfile + env docs + deploy smoke",
        labels=("P0", "foundation", "ops", "ready"),
        body="""**Parent epic:** Foundation

**Outcome**
Port `Dockerfile` / `railway.toml` into this repo; document `CHIRP_*` / `GIT_REF` / secret vars in README. Deploy and prove `/health` + MCP curl.

**Acceptance**
- [ ] Railway service healthy.
- [ ] README deploy section accurate for this repo (not chirp example path).
""",
    ),
    Issue(
        key="f5",
        parent_key="epic-foundation",
        title="Live invocation feed on home (ToolEventBus → SSE)",
        labels=("P1", "foundation", "ready"),
        body="""**Parent epic:** Foundation

**Outcome**
Keep the proven custom `/feed` pattern (or adopt framework `/invocations/live` once aligned with [chirp#983](https://github.com/lbliii/chirp/issues/983)). MCP `tools/call` appears on the landing page within ~1s.

**Acceptance**
- [ ] SSE feed test green.
- [ ] Branded activity row template (can be minimal until Brand epic).
""",
    ),
    # --- Brand children ---
    Issue(
        key="b1",
        parent_key="epic-brand",
        title="Extract design tokens + static assets into app static/",
        labels=("P1", "brand", "design", "ready"),
        body="""**Parent epic:** Brand

**Outcome**
Move `design/styles.css` + `motion.js` (and fonts strategy) into app-served static assets. Define CSS variables (`--void`, `--night`, `--brass`, `--phosphor`, `--signal`, `--glass`) as the product design system.

**Acceptance**
- [ ] App serves shared CSS/JS.
- [ ] Mocks remain as reference under `design/` (or documented as source).
""",
    ),
    Issue(
        key="b2",
        parent_key="epic-brand",
        title="Landing + topbar chrome parity with design/index.html",
        labels=("P1", "brand", "design"),
        body="""**Parent epic:** Brand

**Outcome**
Replace generic host landing with mock-faithful hero: brand-first Orrery., cosmos layer, resolve demo, Gaze/namespace CTAs, steps section. Topbar nav: Gaze · Resolve · Stars · Constellations · Namespaces.

**Acceptance**
- [ ] First viewport matches mock composition rules.
- [ ] Responsive at 860px breakpoint.
""",
    ),
    Issue(
        key="b3",
        parent_key="epic-brand",
        title="Reduced-motion + cosmos/seal/meteor motion parity",
        labels=("P2", "brand", "design"),
        body="""**Parent epic:** Brand

**Outcome**
Port `motion.js` + CSS `@media (prefers-reduced-motion: reduce)` kill-switch. Digest settle, Envelope seal states, constellation stagger, meteor — all respect reduced motion.

**Acceptance**
- [ ] With reduced motion, animations disabled / receipt immediately sealed.
- [ ] With motion allowed, at least seal + digest settle work on live pages.
""",
    ),
    # --- Resolve children (P0 product) ---
    Issue(
        key="r1",
        parent_key="epic-resolve",
        title="Freeze resolve record schema (namespace/name@version)",
        labels=("P0", "resolve", "design", "ready"),
        body="""**Parent epic:** Resolve

**Outcome**
Document and implement the canonical resolve record:

`endpoint`, `key_id`, `content_digest`, `price_per_call`, `alg` (+ `name`, `version`, `visibility`, record `kind`: star|constellation).

Naming: `namespace/name@version` as in mocks (`orrery/html-to-pdf@1.2.0`).

**Acceptance**
- [ ] Schema in code + short docs section.
- [ ] Fixture records for public star + private constellation.
""",
    ),
    Issue(
        key="r2",
        parent_key="epic-resolve",
        title="Implement GET /resolve?name= HTTP API",
        labels=("P0", "resolve", "design"),
        body="""**Parent epic:** Resolve

**Outcome**
HTTP Skill DNS matching the mock contract panel:

`GET /resolve?name=orrery/html-to-pdf` → JSON with endpoint, key_id, content_digest, price_per_call, alg.

**Acceptance**
- [ ] 200 for known names; fail-loud 404 for unknown.
- [ ] Version pin `name@version` honored when present.
""",
    ),
    Issue(
        key="r3",
        parent_key="epic-resolve",
        title="MCP resolve tool returns DNS record (not console URL)",
        labels=("P0", "resolve"),
        body="""**Parent epic:** Resolve

**Outcome**
Replace dogfood `resolve_name` stub. MCP `resolve` returns the same fields as HTTP resolve (endpoint, digest, pubkey/key_id, price, alg).

**Acceptance**
- [ ] MCP + HTTP field parity tested.
- [ ] Agent can call resolve without browsing HTML.
""",
    ),
    Issue(
        key="r4",
        parent_key="epic-resolve",
        title="Resolve console UI (zone table + lookup)",
        labels=("P1", "resolve", "design", "brand"),
        body="""**Parent epic:** Resolve

**Outcome**
Live `design/resolve.html`: lookup parses `name` / `namespace/name` / `name@version`; zone table from API; deep-link to star or constellation; optional digest-settle animation.

**Acceptance**
- [ ] Lookup highlights/resolves a live row.
- [ ] Star vs constellation routing by kind.
""",
    ),
    # --- Gaze children ---
    Issue(
        key="g1",
        parent_key="epic-gaze",
        title="Gaze catalog model + match(intent) tool",
        labels=("P1", "gaze", "design"),
        body="""**Parent epic:** Gaze

**Outcome**
Backing store for gaze hits with kinds `star` | `constellation` | `tool`. Implement `match(intent)` → `[{ name, blurb, endpoint, price }]` as in `design/gaze.html`.

**Acceptance**
- [ ] match returns ranked/static-demo hits from catalog.
- [ ] Progressive disclosure: no tool payloads in match results.
""",
    ),
    Issue(
        key="g2",
        parent_key="epic-gaze",
        title="Gaze MCP tools: search, describe, list_constellations",
        labels=("P1", "gaze"),
        body="""**Parent epic:** Gaze

**Outcome**
Complete public gaze toolset from mocks: `search`, `describe`, `list_constellations` (plus `match` / `resolve` shared with Resolve epic).

**Acceptance**
- [ ] tools/list on gaze node exposes the set.
- [ ] describe returns manifest-ish metadata without executing tools.
""",
    ),
    Issue(
        key="g3",
        parent_key="epic-gaze",
        title="Gaze console UI wired to live MCP/API",
        labels=("P1", "gaze", "design", "brand"),
        body="""**Parent epic:** Gaze

**Outcome**
Replace Alpine static `nodes`/`hits` in `design/gaze.html` with live data. Keep node switcher UX (public sky first; namespace nodes may stub until Namespaces epic).

**Acceptance**
- [ ] Searching/matching updates results from server.
- [ ] Agent call shape panel stays accurate to live tools.
""",
    ),
    # --- Call children ---
    Issue(
        key="c1",
        parent_key="epic-call",
        title="Star detail page from live resolve/describe",
        labels=("P1", "call", "design", "brand"),
        body="""**Parent epic:** Call / Envelope

**Outcome**
`design/star.html` as a live page: endpoint, tools, digest, key_id/alg, oracle pills, price, copy-MCP-URL action.

**Acceptance**
- [ ] Page loads for a known star id/name.
- [ ] Copy MCP URL writes `mcp://…/s/{skill}` to clipboard.
""",
    ),
    Issue(
        key="c2",
        parent_key="epic-call",
        title="Envelope receipt panel + verify states",
        labels=("P1", "call", "trust", "design"),
        body="""**Parent epic:** Call / Envelope

**Outcome**
Show last Envelope (`skill`, `version`, `tool`, `input_digest`, `nonce`, `key_id`, `alg`, `payment_id`) with seal animation states and verify-ok / forge-fail. Use Chirp Envelope crypto — do not reimplement signing.

**Acceptance**
- [ ] Valid envelope shows Verified.
- [ ] Tampered payload fails closed in UI/API verify helper.
""",
    ),
    Issue(
        key="c3",
        parent_key="epic-call",
        title="Demo star MCP endpoint (html-to-pdf stub OK)",
        labels=("P1", "call"),
        body="""**Parent epic:** Call / Envelope

**Outcome**
Ship `mcp://…/s/html-to-pdf` (or equivalent) with tools `convert` + `health` as in mocks. Stub conversion is fine if Envelope + digest fields are real.

**Acceptance**
- [ ] tools/call returns signed Envelope.
- [ ] Star page can display the resulting receipt.
""",
    ),
    # --- Namespace children ---
    Issue(
        key="n1",
        parent_key="epic-namespace",
        title="Decide tenant routing model (subdomain vs path)",
        labels=("P2", "namespace", "design"),
        body="""**Parent epic:** Namespaces

**Outcome**
ADR: `mcp://acme.orrery.dev/…` (mock) vs path-based tenancy for MVP. Document DNS/host requirements for Railway.

**Acceptance**
- [ ] Written decision in repo docs.
- [ ] Follow-on issues updated to match.
""",
    ),
    Issue(
        key="n2",
        parent_key="epic-namespace",
        title="Create namespace provisioning flow",
        labels=("P2", "namespace", "design"),
        body="""**Parent epic:** Namespaces

**Outcome**
Turn “Create namespace” from `design/namespace.html` into a real flow that creates a scoped catalog prefix (`acme/*`) and private resolve zone.

**Acceptance**
- [ ] New namespace appears in resolve with private pills.
- [ ] Fail-loud on reserved/invalid names.
""",
    ),
    Issue(
        key="n3",
        parent_key="epic-namespace",
        title="Caller allowlists + Envelope retention hooks",
        labels=("P3", "namespace", "trust"),
        body="""**Parent epic:** Namespaces

**Outcome**
Minimal allowlist for machine callers and retention policy hooks mentioned on the namespace mock (audit export can be stubbed).

**Acceptance**
- [ ] Unauthorized caller denied on private MCP paths.
- [ ] Retention policy configurable (even if storage is local).
""",
    ),
    # --- Constellation children ---
    Issue(
        key="k1",
        parent_key="epic-constellation",
        title="Constellation record type + policy graph model",
        labels=("P2", "constellation", "design"),
        body="""**Parent epic:** Constellations

**Outcome**
Data model for constellations: nodes, edge types (**gate**, **repair loop** with bound, **fan-in**), `policy_digest`, cross-namespace star refs (`html-to-pdf*`).

**Acceptance**
- [ ] Fixture for `acme/launch-gate` matching the mock graph.
- [ ] Resolve kind discriminates constellation vs star.
""",
    ),
    Issue(
        key="k2",
        parent_key="epic-constellation",
        title="Constellation graph viewer (read-only)",
        labels=("P2", "constellation", "design", "brand"),
        body="""**Parent epic:** Constellations

**Outcome**
Render live policy as SVG/HTML graph with legend (gate/loop/fan-in), inspired by `design/constellation.html`. Authoring editor is out of scope.

**Acceptance**
- [ ] Viewer loads from constellation record.
- [ ] Reduced-motion: no staggered edge draw.
""",
    ),
    Issue(
        key="k3",
        parent_key="epic-constellation",
        title="Constellation MCP: run / status / explain_policy",
        labels=("P2", "constellation"),
        body="""**Parent epic:** Constellations

**Outcome**
MCP node tools from docs-gate mock:

- `run` with Doc Bundle `{ pages, links, examples }` → composite Envelope chain
- `status` → in-flight / completed chain
- `explain_policy` → plain-language gates/loops/fan-in

Steps may be stubbed; composite receipt format must be real.

**Acceptance**
- [ ] tools/list exposes the three tools.
- [ ] run returns chained step receipts (secret-scan → … → release style).
""",
    ),
    # --- Trust children ---
    Issue(
        key="t1",
        parent_key="epic-trust",
        title="Surface publish-oracle status on resolve/star",
        labels=("P2", "trust"),
        body="""**Parent epic:** Trust & Commerce

**Outcome**
Show `check · freeze · smoke` / oracle pill from Chirp reliability/publish results on resolve rows and star pages.

**Acceptance**
- [ ] Skills that fail smoke do not show oracle-ok.
- [ ] Console reliability and public oracle pill agree.
""",
    ),
    Issue(
        key="t2",
        parent_key="epic-trust",
        title="Pricing fields + charge-on-verify / refund stubs",
        labels=("P2", "commerce", "trust"),
        body="""**Parent epic:** Trust & Commerce

**Outcome**
Carry `price_per_call` and Envelope `payment_id` end-to-end. Implement explicit stub hooks for charge-on-verify and refund-on-forge (logged, not silent). Real PSP later.

**Acceptance**
- [ ] Resolve/gaze include price.
- [ ] Verify failure invokes refund stub; success invokes charge stub.
""",
    ),
]


def main() -> None:
    created: dict[str, int] = {}
    for issue in ISSUES:
        created[issue.key] = create_issue(issue.title, list(issue.labels), issue.body)

    # Wire sub-issues (parent first)
    for issue in ISSUES:
        if issue.parent_key is None:
            continue
        parent = created[issue.parent_key]
        child = created[issue.key]
        try:
            add_sub_issue(parent, child)
        except SystemExit as exc:
            print(f"WARN: could not link #{child} to #{parent}: {exc}", file=sys.stderr)

    print("\nDone. Map:")
    for key, number in created.items():
        print(f"  {key}: #{number}")


if __name__ == "__main__":
    main()
