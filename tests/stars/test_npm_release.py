import json

from stars.npm_release.contract import PACKAGE_PATHS
from stars.npm_release.service import get

SOURCE = json.dumps(
    {
        "name": "zod",
        "version": "4.0.0",
        "description": "x",
        "license": "MIT",
        "engines": {"node": ">=18"},
        "dist": {"tarball": "https://x", "integrity": "sha512-x", "shasum": "abc"},
        "dependencies": {"a": "1"},
    }
).encode()
URL = "https://registry.npmjs.org/zod/latest"


def test_canonical_fixture_and_unknown_no_fetch() -> None:
    result = get("zod", fetch=lambda url, **_: (url, 200, {"ETag": "tag"}, SOURCE))
    assert (
        result["version"] == "4.0.0"
        and result["dist"]["integrity"] == "sha512-x"
        and result["etag"] == "tag"
    )

    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert get("nope", fetch=fail)["error"] == "package_not_allowed"


def test_malformed_escape_and_encoded_scope() -> None:
    assert (
        get(
            "zod",
            fetch=lambda _url, **_: ("https://registry.npmjs.org/nope/latest", 200, {}, SOURCE),
        )["error"]
        == "redirect_not_allowed"
    )
    assert get("zod", fetch=lambda url, **_: (url, 200, {}, b"bad"))["error"] == "source_malformed"
    assert PACKAGE_PATHS["@modelcontextprotocol/sdk"] == "%40modelcontextprotocol%2Fsdk/latest"
