# Place-hours allowlist

`orrery/place-hours` resolves an allowlisted **venue token** to weekly hours and
an open-now flag using an offline fixture table only. There is no Google Places
API, venue search egress, or arbitrary location lookup.

Initial venue tokens: `central-park-cafe-nyc`, `british-museum-london`,
`tokyo-ramen-yokocho`, `griffith-cafe-la`, `opera-bar-sydney`,
`art-institute-cafe-chicago`, and `louvre-cafe-paris`. Requests for unknown
venue tokens fail with `venue_not_allowed`. The star is not a trip planner or
open-ended restaurant finder.

Optional `as_of` (ISO-8601) pins the instant used for open-now evaluation;
otherwise the call-time clock applies. Attribution on successful calls uses
`provider: "orrery-fixtures"`.
