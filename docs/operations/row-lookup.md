# Row Lookup

`orrery/row-lookup` is a narrow, stateless exact lookup over the canonical
Vega `flights-airport.csv` dataset. It accepts only
`dataset: "flights-airport"` and a key with exactly two uppercase IATA fields:
`{"origin": "ABE", "destination": "ATL"}`. It does not accept a URL, SQL,
filter language, or arbitrary query.

The Star fetches only the documented exact raw GitHub path over HTTPS, denies
redirects, caps downloads at eight seconds/512 KiB and scans at most 10,000
rows. It returns one typed `{origin, destination, count}` row or an explicit
`row_not_found` result with source evidence. No source data or lookup state is
stored. `csv-url` is the broader bounded sample reader for the same family of
sources; this Star is the safer single-key retrieval path when the source key
shape is known.
