# npm Release
`orrery/npm-release` fetches only the latest-dist-tag documents for allowlisted `zod` and `@modelcontextprotocol/sdk`, using the canonical registry endpoint and encoded scoped path. It does not read full packument history. Responses are HTTPS-only/no-redirect, bounded to 8 seconds/512 KiB; npm registry rate limits apply, so callers should retain receipts rather than poll.
