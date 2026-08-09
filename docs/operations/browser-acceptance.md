# Public browser acceptance

The browser harness verifies the public, local artifact-delivery path without
using a signed-in browser or any personal credentials. It resolves the known
`orrery/html-to-pdf` Star, invokes its public direct MCP endpoint, downloads
the returned PDF through the browser, and verifies response headers and
SHA-256 bytes.

Install Chromium once in a CI image or a local development machine:

```bash
uv run playwright install --with-deps chromium
ORRERY_BROWSER_ACCEPTANCE=1 uv run pytest -m browser
```

The test creates its own local host, uses `ORRERY_ARTIFACT_BACKEND=memory`, and
uses Playwright's fresh browser context. It does not call Railway or any public
production endpoint. On failure it emits only `failure.json` (current URL,
last console messages, and compact response/request-failure summaries) plus a
failure screenshot under pytest's temporary directory. Successful runs leave
no screenshots.

## DevTools diagnosis without a personal session

For an interactive failure diagnosis, start the local host with the same
environment as the test, then launch Chrome with a new disposable profile. Do
not attach the normal Chrome profile, sign in, install extensions, or visit a
non-local endpoint:

```bash
ORRERY_SKIP_PUBLISH=1 ORRERY_ARTIFACT_BACKEND=memory uv run python app.py
google-chrome --user-data-dir="$(mktemp -d)" --remote-debugging-port=9222 http://127.0.0.1:8000/resolve?name=orrery/html-to-pdf
```

Use Chrome DevTools only to inspect the local Network and Console panels, or
attach a DevTools MCP client to that disposable profile for developer
diagnosis. This is an operator/developer workflow, not a public Star: no
Orrery Star receives browser-control tools, session cookies, or profile access.
