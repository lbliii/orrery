# Certificate expiry allowlist

`orrery/cert-expiry` accepts only named hosts: `orrery-public` and
`python-docs`. It always uses validated TLS with SNI and port 443. It does not
accept a hostname or port from callers and is not a certificate scanner.
