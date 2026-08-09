# GitHub File at Ref
`orrery/gh-file-at-ref` retrieves only fixed Orrery files and only when callers provide a full lowercase 40-hex commit SHA. It never accepts branches, tags, paths, repositories, or URLs. GitHub API rate limits apply; the canonical HTML URL is pinned to the requested SHA, and callers should retain the receipt rather than poll.
