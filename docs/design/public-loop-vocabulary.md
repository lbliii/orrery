# Design: Public loop vocabulary

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-14
- **Parent:** [caller-trust-a-tier.md](./caller-trust-a-tier.md)
- **Epic:** [#426](https://github.com/lbliii/orrery/issues/426)
- **Design issue:** [#428](https://github.com/lbliii/orrery/issues/428)
- **Binds:** [ADR 0005](../adr/0005-discovery-and-dual-trust.md),
  [ADR 0010](../adr/0010-aggregate-mcp-call-skill.md)

## Question frozen

What words may public pages use for the pointing loop and for aggregate
`/mcp`, given ADR 0010 shipped `call_skill` on the advertised URL?

## Decision

### Loop (every human surface)

**Gaze → resolve → call → seal.** Four named steps. Do not drop Gaze.
Do not rename Seal to Verify on the homepage step list.

- **Verify** remains the *act* (“verify the Envelope or don’t treat it
  as done”). It is not a fourth/third step name that replaces Seal.
- Homepage vitals label **Seals** may stay; add a one-line gloss if the
  leaf touches that strip.
- Fix the `verifyable` typo → `verifiable`.

### Commerce honesty

Do not say “Pay only for truth” on the homepage while the catalog is
Free and the wallet is a stub. Use verify/seal language. Pricing page
honesty (“Free is a catalog label”) stays.

### Aggregate `/mcp`

One sentence, reused:

> Slim discovery plus one `call_skill` forwarder. Publisher mounts stay
> canonical (ADR 0004).

Forbidden on public pages: “legacy bridge”, “discovery only” for the
default `/mcp` that already lists `call_skill`.

Gaze kicker must not say **route** (fights “not a skill router”).
Prefer “browse · point · don’t install”.

### Kida on `/connect`

Keep the shipped Kida demo. It is not the category hero. The first
“start here” block teaches the four-step loop (teaching trio remains
the anti-install parable). Do not delete Kida in this pass.

### Page errors (humans)

Pages may map known `body.error` codes to one sentence + next action.
Unknown codes: generic human line; still show the code in `<code>` for
agents. Never display raw exception strings.

JSON/MCP codes stay snake_case. Pages annotate; they do not replace.
