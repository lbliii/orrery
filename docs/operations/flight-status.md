# Flight status allowlist

`orrery/flight-status` resolves an allowlisted **flight id** and **date** to
schedule and status fields using an offline fixture table only. There is no
live airline API egress or open-ended flight lookup.

Initial flight ids: `AA100`, `UA456`, `DL789`, and `BA178`. Pinned fixture
dates: `2026-08-11` and `2026-08-12` (where scheduled). Requests for unknown
flight ids fail with `flight_not_allowed`; unknown dates fail with
`date_not_available`. The star is not a trip planner or live tracker.

Attribution on successful calls uses `provider: "orrery-fixtures"`.
