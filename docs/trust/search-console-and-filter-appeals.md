# Search Console and filtering appeals

These are user-owned external steps. This repository does not claim they have
been completed, and no automated script submits them on the owner's behalf.

1. Verify the custom domain in Google Search Console with the DNS TXT record
   supplied by Search Console; keep the record in DNS for the verification
   period.
2. Submit `https://orrery.lol/sitemap.xml` after verification and review the
   indexing/crawl status there.
3. For a browser, enterprise, or security-vendor block, collect the vendor
   name, exact block/error text, timestamp, URL, screenshot or response body,
   and whether the failure reproduces on an independent network.
4. Submit a targeted reclassification or allowlist request to that vendor with
   the evidence, public security contact, terms/privacy pages, and a concise
   explanation of Orrery's bounded MCP behavior.

Use the external GitHub Action result from the public-domain canary to separate
an origin failure from a local/work-network interception before making DNS or
Railway changes.
