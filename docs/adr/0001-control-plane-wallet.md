# ADR 0001: Control plane, reactive stars, prepaid wallet

- **Status:** Accepted (strategy freeze)
- **Date:** 2026-08-08
- **Issues:** [#36](https://github.com/lbliii/orrery/issues/36), saga [#1](https://github.com/lbliii/orrery/issues/1)
- **Epics:** [#6](https://github.com/lbliii/orrery/issues/6) Call/Envelope, [#8](https://github.com/lbliii/orrery/issues/8) Constellations, [#9](https://github.com/lbliii/orrery/issues/9) Trust & Commerce

## Context

Orrery is Skill DNS + escrow for paid expertise — not a skill host, not an LLM
wrapper, not a catalog of repos. Agents gaze → resolve → call publisher →
verify Envelope. Money moves only when an Envelope verifies. Wave 0 pointing
loop is green; Wave 2 needs a frozen decision log before ledger/Stripe code.

## Decisions

### 1. Control plane vs data plane (no proxy-all-calls)

| Plane | Owner | Responsibility |
| --- | --- | --- |
| **Control** | Orrery | Gaze, Skill DNS resolve, catalog, wallet/ledger, tenancy, constellation orchestration, brand |
| **Data / execute** | Publisher | Skill process, live APIs, private corpora, reactive bodies |
| **Transport / seal** | Chirp | `chirp.skill`, Envelope signing, publish oracle |
| **Reactive body (optional)** | Kida | Templates/bindings that inject live data at call time |

Orrery must **not** reverse-proxy or execute everyone’s tools. Dogfood skills
on this host are demos only. Call path is **agent → publisher MCP**.

### 2. Skill-shaped everything

Everything gateable is a **star** (resolvable skill). Reports, APIs, and
expertise are stars with tools — no separate Content/CMS object in v1.
Constellations are composite skill graphs; namespaces are tenancy.

### 3. Reactive stars

Resolve pins **identity/contract** (`endpoint`, digest, key, price, alg).
Call injects a **live payload** at call time (Chirp skill ± optional Kida
body). Offline clones go stale; value is the live truth, not a frozen blob.

### 4. Prepaid wallet

- Starter balance **$5** (integer cents on the ledger).
- **Burn on Envelope verify** (capture after soft hold at call).
- **Stripe top-up only** — never per-call card auth / micropayments.
- Hot path (resolve, hold, verify) must not call Stripe.
- Wave 0 adjacent: loud charge/refund **stubs** only (`commerce.*_stub`).

See [0002](./0002-prepaid-wallet-ledger.md) and [0003](./0003-stripe-topup.md).

### 5. Conditionals / constellation budgets

Light `if` inside a single star is fine. Real branching lives in
**constellations** with hard **step budgets / timeouts**. Default toll:
**debit on terminal verified composite** (per-node tolls later).

### 6. S-tier bar

Acceptance flavor for product work:

- **Ergonomic:** one loop; agent-native MCP; actionable insufficient-balance.
- **Performant:** resolve + wallet gate cheap/local; call is agent→publisher;
  gaze returns no valuable payload.
- **Sticky:** verified Envelopes in downstream gates; live stars stale offline;
  namespace allowlists.
- **Scalable:** Orrery stays DNS+ledger shaped; publishers scale compute;
  constellation step budgets.

### 7. Explicit Not now

- Untrusted third-party marketplace + isolate sandbox
  (opt-in **listing** + crowdsourced pills is a carve-out — [ADR 0012](./0012-opt-in-listing.md); still no isolate, proxy-all, payouts, or essays)
- Scale-to-zero FaaS / Orrery-as-compute-host / **proxy-all-calls**
- BYO-key-per-invocation marketplace
- Separate Document/Content CMS object
- **Stripe charges per tool call**
- Constellation authoring editor (viewer + run first)
- Full publisher payouts (ledger may record `publisher_share_cents` early)
- Wallet/Stripe **implementation** before Wave 0+1 exit criteria (design OK now)

## Consequences

- Agents and humans cite this ADR + saga #1 for strategy disputes.
- Epics #6 / #8 / #9 stay aligned: call path is publisher-direct; constellation
  budgets are first-class; commerce is stubs → prepaid wallet → payouts later.
- Implementation of ledger (#38) and Stripe (#39) is gated on design acceptance
  and Wave 0+1 green — not on this ADR alone.

## Links

- Saga: https://github.com/lbliii/orrery/issues/1
- ADR ticket: https://github.com/lbliii/orrery/issues/36
- Ledger design: [0002-prepaid-wallet-ledger.md](./0002-prepaid-wallet-ledger.md)
- Stripe design: [0003-stripe-topup.md](./0003-stripe-topup.md)
