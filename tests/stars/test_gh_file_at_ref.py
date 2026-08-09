import json

from stars.gh_file_at_ref.service import get

REF = "a" * 40
URL = f"https://api.github.com/repos/lbliii/orrery/contents/README.md?ref={REF}"
SOURCE = json.dumps(
    {"content": "IyBP\nc nJlcnk=\n".replace(" ", ""), "sha": "blob", "type": "file"}
).encode()


def test_canonical_base64_and_prefetch_rejection() -> None:
    result = get("orrery-readme", REF, fetch=lambda url, **_: (url, 200, {}, SOURCE))
    assert (
        result["source_url"] == URL
        and result["text_slice"] == "# Orrery"
        and result["blob_sha"] == "blob"
    )

    def fail(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert (
        get("no", REF, fetch=fail)["error"] == "target_not_allowed"
        and get("orrery-readme", "main", fetch=fail)["error"] == "invalid_ref"
    )


def test_malformed_and_escape() -> None:
    assert (
        get(
            "orrery-readme",
            REF,
            fetch=lambda _url, **_: ("https://api.github.com/repos/x", 200, {}, SOURCE),
        )["error"]
        == "redirect_not_allowed"
    )
    assert (
        get("orrery-readme", REF, fetch=lambda url, **_: (url, 200, {}, b"bad"))["error"]
        == "source_malformed"
    )
