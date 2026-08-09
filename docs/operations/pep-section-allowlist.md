# PEP Section allowlist

`orrery/pep-section` fetches canonical HTML directly from `peps.python.org`,
not a GitHub mirror. It permits only PEP 8 (`Introduction`, `Code Layout`) and
PEP 517 (`Build backend interface`), with no arbitrary PEP number, URL, or
section. Fetches are HTTPS-only, redirect denied, eight seconds, and 512 KiB.
The heading-aware extractor selects the final matching body heading, avoiding
table-of-contents duplicates.
