# Table Diff

`orrery/table-diff` is a pure in-memory transform: it stores nothing, performs
no network access, and accepts only two bounded caller-provided snapshots plus
an explicit unique key column. Each snapshot permits at most 100 rows, 25
columns, short JSON scalar values, and 64 KiB serialized input across both
snapshots. Rows are canonicalized deterministically before comparison.

The Star returns independently computed `snapshot_digest` values for the
canonical rows. An optional caller `digest` is preserved separately as a
`caller_digest_claim`; it is evidence supplied by the caller, not trusted or
recomputed as the same thing. To compose with `orrery/csv-url`, pass its
bounded `rows` with its `source_digest` as that claim. The resulting table
digest proves the exact transformed snapshot Orrery compared, while the claim
preserves provenance back to the CSV source.
