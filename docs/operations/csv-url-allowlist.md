# CSV URL dataset allowlist

`orrery/csv-url` does not fetch caller-provided URLs. It offers only the
`cars`, `airports`, and `seattle-weather` CSV files from the documented Vega
Datasets repository paths on `raw.githubusercontent.com`:

- `vega/vega-datasets/main/data/cars.csv`
- `vega/vega-datasets/main/data/airports.csv`
- `vega/vega-datasets/main/data/seattle-weather.csv`

The requested key maps to one exact HTTPS URL. Redirects and final-path
changes are rejected; downloads are limited to eight seconds and 512 KiB. CSV
is parsed in memory only—Orrery does not create a CSV database or system of
record—and responses return at most 100 typed rows.
