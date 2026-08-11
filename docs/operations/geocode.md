# Geocode allowlist

`orrery/geocode` resolves an allowlisted **place token** to coordinates and a
display name using an offline fixture table only. There is no Google Maps API,
geocoder egress, or arbitrary address lookup.

Initial place tokens: `new-york`, `london`, `tokyo`, `los-angeles`, `sydney`,
`chicago`, and `paris`. Requests for unknown place tokens fail with
`place_not_allowed`. The star is not a trip planner or open-ended geocoder.

Attribution on successful calls uses `provider: "orrery-fixtures"`.
