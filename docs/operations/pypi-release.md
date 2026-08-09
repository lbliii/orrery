# PyPI Release
`orrery/pypi-release` fetches only the current PyPI JSON metadata for `httpx` or `pydantic`. It reports `info.version` and files for that current release, not a historical or security-complete package audit. Calls are HTTPS-only, exact canonical endpoint/no redirects, eight seconds and 1 MiB. PyPI rate limits apply; callers should cache receipts rather than poll.
