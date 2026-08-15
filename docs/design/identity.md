# Orrery identity

Orrery is a night observatory for Skill DNS. Agents and humans *point* at
hosted truth — they do not install packages. Catalogs hand you a repo; Orrery
hands you an endpoint, a digest, and a receipt so the agent can keep moving.

**Skills you point at, not install.**

## Metaphor map

| Verb | Product meaning | Visual cue |
| --- | --- | --- |
| **Gaze** | Discover / match intent against a sky | Node picker, ranked hits |
| **Resolve** | Lock identity (endpoint, digest, key, price) | Stacked zone plates, brass settle flash |
| **Call** | Invoke at the publisher (Orrery is not the proxy) | Live feed of tool events |
| **Seal** | Prove the result (Envelope) | Receipt panel, phosphor verify |

Supporting nouns: **star** (callable skill), **constellation** (drawn policy
graph), **namespace** (private tenancy), **orb** (brand instrument),
**cosmos** (shared sky).

## Soft bind

Product vocabulary stays celestial. Structural UI stays plain.

| Kind | Names | Examples |
| --- | --- | --- |
| Product / copy | Celestial | gaze, resolve, star, constellation, namespace |
| Signature widgets | Metaphor allowed | `.cosmos`, `.orb`, `.receipt`, `.constellation` |
| Structural UI | Plain | `.panel`, `.pill`, `.btn`, `.record-table`, `.meta-list` |

New UI defaults to plain structural names. Reserve metaphor class names for
signature widgets and product copy — not every button becomes a “star.”

## Principles

**Do**

- Brass instruments in deep space: sparse chrome, sharp `--radius` (2px).
- Mono for machine truth; display for chrome; serif for human prose.
- Brass for lock / commit; phosphor for verified; fog/mist for secondary.
- First viewport = one composition: brand, one claim, one CTA group, one
  visual anchor.
- Sparse motion that respects `prefers-reduced-motion`.

**Don’t**

- Purple SaaS, card grids, or ChirpUI generic skins.
- Dashboard chrome on brand surfaces (stats strips, pill clusters, floating
  badges).
- Hard-clip glow or atmosphere with parent `overflow: hidden` unless a soft
  mask fades the effect to transparent first.

## Voice

Short. Precise. Instrument-manual — not hype.

Write like a plate on a telescope: name the control, state what it locks,
stop. Prefer verbs from the metaphor map. Prefer concrete machine nouns
(digest, endpoint, Envelope) over marketing abstractions.

## Reference

- Live styles: [`static/styles.css`](../../static/styles.css)
- Validated mocks: [`design/`](../../design/)
- Frozen favorite: [`design/v1-night-gold/`](../../design/v1-night-gold/)
- System inventory: [`system.md`](./system.md)
