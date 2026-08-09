# RFC Section allowlist

`orrery/rfc-section` accepts only RFC 9110 sections 3.1/4 and RFC 9111 section
4 from canonical RFC Editor plain text. It does not accept an arbitrary RFC
number, section, URL, or redirect target. Fetches are HTTPS-only, redirect
denied, limited to 8 seconds and 512 KiB.
