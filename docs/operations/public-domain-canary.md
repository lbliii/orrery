# Public-domain canary

Run `python scripts/canary_public_domain.py --origin https://orrery.lol` to
check the public custom domain from the caller's network. The scheduled GitHub
Action runs daily and can also be started manually; it is intentionally
nonblocking so an external reachability incident does not block repository CI.

The canary uses ordinary HTTPS hostname validation. It checks homepage identity,
required `security.txt` fields, the Orrery trust facts, sitemap origin, and the
MCP server-card. It deliberately does not pin an IP address or CNAME target:
Railway can rotate those safely behind the custom hostname.

## Flake policy

Browser security products and work-network filters can inject a block page or
intercept TLS/DNS locally. Treat a local/browser failure as evidence, not proof
that Railway or DNS is broken. Compare the GitHub Action's external result
before changing Railway, DNS, or application configuration. Preserve the
returned vendor page, error code, timestamp, requested URL, and network context
when escalating a filter-specific problem.
