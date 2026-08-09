"""Repeatable public-browser acceptance coverage for artifact delivery (#142).

Run explicitly after installing the Playwright Chromium binary:
``ORRERY_BROWSER_ACCEPTANCE=1 uv run pytest -m browser``.
The browser owns a temporary profile and talks only to a local test host.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_URL = re.compile(r"'artifact_url': '([^']+)'")
_SHA256 = re.compile(r"'sha256': '(sha256:[0-9a-f]{64})'")


def _browser_enabled() -> bool:
    return os.environ.get("ORRERY_BROWSER_ACCEPTANCE", "").lower() in {"1", "true", "yes"}


@contextmanager
def _local_host() -> Iterator[str]:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {
        **os.environ,
        "PORT": str(port),
        "CHIRP_ENV": "development",
        "CHIRP_DEBUG": "0",
        "CHIRP_SECRET_KEY": "browser-acceptance-test-secret",
        "ORRERY_SKIP_PUBLISH": "1",
        "ORRERY_ARTIFACT_BACKEND": "memory",
        "ORRERY_WORLD_TIME_JSON": json.dumps({"dateTime": "2026-08-09T12:00:00"}),
    }
    process = subprocess.Popen(
        [sys.executable, "app.py"], cwd=ROOT, env=environment, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                with urlopen(f"{base_url}/health", timeout=0.2) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("local Orrery test host did not become healthy")
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


@contextmanager
def _failure_evidence(page: Any, evidence_dir: Path) -> Iterator[None]:
    """Persist compact diagnostics only for a failed browser acceptance run."""
    console: list[str] = []
    responses: list[dict[str, Any]] = []
    failures: list[str] = []
    page.on("console", lambda message: console.append(f"{message.type}: {message.text}"))
    page.on(
        "response",
        lambda response: responses.append({"url": response.url, "status": response.status}),
    )
    page.on("requestfailed", lambda request: failures.append(f"{request.url}: {request.failure}"))
    try:
        yield
    except Exception:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "failure.json").write_text(
            json.dumps(
                {
                    "url": page.url,
                    "console": console[-20:],
                    "responses": responses[-30:],
                    "failed_requests": failures[-20:],
                },
                indent=2,
            )
        )
        page.screenshot(path=str(evidence_dir / "failure.png"), full_page=True)
        raise


@pytest.mark.browser
@pytest.mark.issue(142)
def test_public_pdf_delivery_in_a_disposable_headless_browser(tmp_path: Path) -> None:
    if not _browser_enabled():
        pytest.skip("set ORRERY_BROWSER_ACCEPTANCE=1 after installing Playwright Chromium")
    playwright = pytest.importorskip("playwright.sync_api")
    with _local_host() as base_url, playwright.sync_playwright() as engine:
        browser = engine.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            with _failure_evidence(page, tmp_path / "browser-evidence"):
                page.goto(f"{base_url}/resolve?name=orrery/html-to-pdf", wait_until="networkidle")
                resolved = page.evaluate(
                    """async () => (await fetch('/api/resolve?name=orrery/html-to-pdf')).json()"""
                )
                assert resolved["name"] == "orrery/html-to-pdf"

                called = page.evaluate(
                    """async payload => { const response = await fetch('/stars/html-to-pdf/mcp', {
                    method: 'POST', headers: {'content-type': 'application/json',
                    'mcp-protocol-version': '2025-06-18'}, body: JSON.stringify(payload)});
                    return {status: response.status, body: await response.json()}; }""",
                    {
                        "jsonrpc": "2.0",
                        "id": 142,
                        "method": "tools/call",
                        "params": {"name": "convert", "arguments": {"html": "<h1>Orrery</h1>"}},
                    },
                )
                assert called["status"] == 200
                text = called["body"]["result"]["content"][0]["text"]
                artifact_match, sha256_match = _ARTIFACT_URL.search(text), _SHA256.search(text)
                assert artifact_match is not None and sha256_match is not None, text
                artifact_url, expected_sha256 = artifact_match.group(1), sha256_match.group(1)

                served = page.evaluate(
                    """async url => { const response = await fetch(url); return {
                    status: response.status, contentType: response.headers.get('content-type'),
                    disposition: response.headers.get('content-disposition'),
                    bytes: Array.from(new Uint8Array(await response.arrayBuffer()))}; }""",
                    artifact_url,
                )
                assert served["status"] == 200
                assert served["contentType"].startswith("application/pdf")
                assert "attachment;" in served["disposition"]
                served_sha256 = hashlib.sha256(bytes(served["bytes"])).hexdigest()
                assert served_sha256 == expected_sha256.removeprefix("sha256:")

                with page.expect_download() as expected_download:
                    page.evaluate(
                        """url => { const link = document.createElement('a'); link.href = url;
                        link.id = 'orrery-browser-download';
                        document.body.append(link); link.click(); }""",
                        artifact_url,
                    )
                download = expected_download.value
                assert download.failure() is None
                page.locator("#orrery-browser-download").evaluate("element => element.remove()")
                download_path = tmp_path / download.suggested_filename
                download.save_as(str(download_path))
                downloaded_sha256 = hashlib.sha256(download_path.read_bytes()).hexdigest()
                assert downloaded_sha256 == expected_sha256.removeprefix("sha256:")
        finally:
            context.close()
            browser.close()
