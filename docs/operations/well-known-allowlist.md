# Well-known Star allowlist

`orrery/well-known` accepts only `orrery-llms` and `orrery-mcp-server-card`.
They map to Orrery's official HTTPS discovery documents. The caller cannot
supply a URL or path. The Star uses the local authoritative discovery
generators rather than making an HTTP request back to its own public service,
so it cannot deadlock on a self-fetch. Reads are bounded to 64 KiB and results
contain only a bounded text slice plus metadata/digest.
