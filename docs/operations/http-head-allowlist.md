# HTTP Head allowlist

`orrery/http-head` accepts a named target, not a URL. The initial allowlist is
`python-3.14-whatsnew` (`docs.python.org`) and `timeapi-utc` (`timeapi.io`).
The Star issues HTTP `HEAD` only, rejects redirects that leave these HTTPS
hosts, and returns metadata rather than response bytes. Requests for unknown
targets fail with `target_not_allowed`; clients must not treat this Star as a
general web fetcher.
