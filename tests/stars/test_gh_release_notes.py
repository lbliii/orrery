import hashlib
import json

from stars.gh_release_notes.service import observe

SOURCE = json.dumps(
    {
        "id": 1,
        "tag_name": "v1",
        "name": "One",
        "published_at": "2026-01-01",
        "html_url": "https://github.com/x",
        "draft": False,
        "prerelease": False,
        "body": "notes",
    }
).encode()
URL = "https://api.github.com/repos/pallets/flask/releases/latest"
DIGEST = f"sha256:{hashlib.sha256(b'notes').hexdigest()}"


def test_fixture_digest_changes_and_prefetch_rejection() -> None:
    result = observe("flask", fetch=lambda url, **_: (url, 200, {}, SOURCE))
    assert result["body_digest"] == DIGEST and result["change"] == "unknown"
    assert (
        observe("flask", DIGEST, fetch=lambda url, **_: (url, 200, {}, SOURCE))["change"]
        == "unchanged"
    )
    assert (
        observe("flask", "sha256:old", fetch=lambda url, **_: (url, 200, {}, SOURCE))["change"]
        == "changed"
    )

    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert observe("nope", fetch=fail)["error"] == "target_not_allowed"


def test_escape_and_malformed() -> None:
    assert (
        observe(
            "flask", fetch=lambda _url, **_: ("https://api.github.com/repos/x", 200, {}, SOURCE)
        )["error"]
        == "redirect_not_allowed"
    )
    assert (
        observe("flask", fetch=lambda url, **_: (url, 200, {}, b"bad"))["error"]
        == "source_malformed"
    )
