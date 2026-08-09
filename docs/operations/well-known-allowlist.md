# Well-known Star allowlist

`orrery/well-known` accepts only `orrery-llms` and `orrery-mcp-server-card`.
They map to Orrery's official HTTPS discovery documents. The caller cannot
supply a URL or path. Reads are bounded to 64 KiB, redirects outside
`orrery.lol` are rejected, and results contain only a bounded text slice plus
metadata/digest.
