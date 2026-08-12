# Invite Ready (secretary enrich-before-seal)

`orrery/invite-ready` is the secretary constellation for **enrich-before-seal**:
live UTC clock plus allowlisted flight status, geocode, and venue hours, sealed
in one composite Envelope suitable to attach to a draft invite.

Pipeline: world-time → flight-status → geocode → place-hours → composite seal.

Uses shipped secretary stars only. Google Maps (#139) is out of scope for this
leaf — fixture allowlists, not open geocoding or live airline APIs.

## Inputs

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `place` | no | `new-york` | Allowlisted geocode token |
| `venue` | no | `central-park-cafe-nyc` | Allowlisted venue-hours token |
| `flight` | no | `AA100` | Allowlisted flight id |
| `date` | no | `2026-08-11` | Pinned fixture date |

Venue `open_now` is evaluated against world-time UTC when the clock succeeds.

## Demo path

```python
from stars.invite_ready.service import run

result = run(
    place="new-york",
    venue="central-park-cafe-nyc",
    flight="AA100",
    date="2026-08-11",
)
assert result["status"] in {"enriched", "incomplete"}
assert result["atlas_recommendation"]
assert "components" in result
```

Direct MCP: `POST /constellations/invite-ready/mcp` — tool `run`.

## Atlas recommendation (products)

Attach the signed composite Envelope from `orrery/invite-ready` to draft invites
**before seal**. Call with allowlisted `place`, `venue`, `flight`, and `date`
tokens so clock, flight status, coordinates, and venue hours are sealed together
at call time.

Pidge atlas copy (snippet):

> Before you seal an invite, enrich it with **Invite Ready** — one call seals
> UTC now, flight status, place coordinates, and whether the venue is open.
> Use fixture tokens from coverage; this is not open Maps or live airline lookup.

## Dispositions

| Value | Meaning |
| --- | --- |
| `enriched` | All four secretary components returned complete evidence |
| `incomplete` | One or more components failed; full component payloads retained |

## Ops

- Publisher key env: `ORRERY_INVITE_READY_KEY_ID` (or shared `ORRERY_STAR_*`).
- Member stars: `orrery/world-time`, `orrery/flight-status`, `orrery/geocode`,
  `orrery/place-hours`.
- Acceptance: `uv run pytest -q -k invite_ready`
