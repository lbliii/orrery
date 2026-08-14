# Orrery instrument beats

Named motion only. Leaves do not invent shimmer, Lottie, or view transitions.
Freeze: [#472](https://github.com/lbliii/orrery/issues/472). Tokens live in
[`static/css/tokens.css`](../../static/css/tokens.css). Beat CSS:
[`static/css/motion.css`](../../static/css/motion.css). Wiring:
[`static/motion.js`](../../static/motion.js).

Haptics = tactile visual. Optional `navigator.vibrate(12)` **only** on Seal and
Copy succeeded; never hover/nav; skip when `prefers-reduced-motion`. Reduced
motion jumps to the end state; color and border still change.

## Duration tokens

| Token | Value | Use |
| --- | --- | --- |
| `--tick` | `80ms` | Press |
| `--flash` | `180ms` | Copied / short chrome fades |
| `--settle` | `280ms` | Arrive / settle |
| `--seal` | `360ms` | Seal / constellation edge draw |
| `--ease` | `cubic-bezier(0.22, 1, 0.36, 1)` | Shared curve |

Do not write raw `80` / `180` / `280` / `360ms` in later CSS.

## Beat table

| Beat | Where | Notes |
| --- | --- | --- |
| **Press** | `:active` `--tick` on `.btn` `.gaze-node` `.field` | Tactile; no hover vibrate |
| **Focus** | brass `:focus-visible` only | `.btn` / `.field` ring |
| **Busy** | label “…”, disabled | No spinner kit |
| **Arrive** | gaze hits, `.activity-item.is-arriving`, `.alert` at `--settle` | One-shot on new feed rows; do not re-animate the list |
| **Settle** | `/resolve` **server-matched** digest (`value-settled`) | `initMatchedDigest` |
| **Reveal** | constellation (keep) | `[data-constellation].is-revealed` |
| **Seal** | `[data-receipt]` on star detail | `initStarReceipt` + vibrate(12) |
| **Copied** | `[data-copy-mcp].is-copied` + `--flash` | JS reads `--flash`; vibrate(12) on success |
| **Live** | `.live-dot` (keep) | Phosphor pulse |

No load-theater `rise` on `.resolve-demo` or `.hero-copy`. Atmosphere may loop;
plates do not.

## Reduced motion

`prefers-reduced-motion: reduce` stops continuous sky/orb/live-dot animation
and jumps Press / Arrive / Settle / Seal to the end state. Brass focus rings
and `--danger` / `--phosphor` color and border changes remain.
