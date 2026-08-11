# Timezone resolve allowlist

`orrery/tz-resolve` resolves an IANA timezone from either a **named allowlisted
place token** or a **lat/lon pair** using offline lookup only. There is no
geocoding API, Maps provider, or open-web browse.

Initial place tokens: `new-york`, `london`, `tokyo`, `los-angeles`, `sydney`,
`chicago`, and `paris`. Requests for unknown place tokens fail with
`place_not_allowed`. Lat/lon pairs outside the offline region table fail with
`coordinates_not_resolved`. The star is not a trip planner.
