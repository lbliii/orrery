# Row Validate

`orrery/row-validate` is a local, stateless validator. Its initial static
`flights-airport` profile matches `row-lookup` and `csv-url`: exactly
`origin`/`destination` uppercase three-letter IATA-like strings and a
nonnegative integer `count`; extra fields are rejected. The profile digest is
deterministic and identifies the schema used for the result.

The profile derives from the documented Vega `flights-airport.csv` shape. If
that source changes, update this static profile, its version, tests, and
documentation together before publishing a new Star version. No schema is
fetched at validation time.
