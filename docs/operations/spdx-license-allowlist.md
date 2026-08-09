# SPDX License allowlist

`orrery/spdx-license` accepts only `MIT`, `Apache-2.0`, `BSD-3-Clause`, and
`MPL-2.0`. Each request is fetched only from its generated canonical SPDX JSON
endpoint, `https://spdx.org/licenses/{ID}.json`; callers cannot supply a URL.
Responses are HTTPS-only, redirects are denied, and the fetch is limited to
eight seconds and 512 KiB. The result links to the matching human-readable
`https://spdx.org/licenses/{ID}.html` page and returns bounded license text.
