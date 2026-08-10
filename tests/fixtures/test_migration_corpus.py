"""Migration corpus golden fixtures (#168).

Public/synthetic repositories and stage digests for MyST→MDX and OpenAPI
profiles per ADR 0008. Regression gate for profile publication — no private
customer content.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

import pytest

_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "migration"
_PROFILE_DIR = _CORPUS_ROOT / "profiles"
_MANIFEST_PATH = _CORPUS_ROOT / "corpus.v1.json"
_UNSAFE_HARNESS_PATH = _CORPUS_ROOT / "unsafe_harness.v1.json"

_REQUIRED_PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "profile_id",
        "version",
        "source",
        "target",
        "feature_vocabulary",
        "compatibility_policy",
        "execution_locality",
        "transformer",
        "validator",
        "retention_redaction",
        "profile_digest",
    }
)
_ALLOWED_OPTIONAL_PROFILE_FIELDS = frozenset({"title", "description", "supersedes"})
_FORBIDDEN_ROOT_PROFILE_FIELDS = frozenset({"family", "latest", "side_channel"})
_FEATURE_CLASSES = frozenset(
    {"safe", "transformable", "decision_required", "unsupported", "malformed"}
)
_FLOATING_TOKENS = frozenset({"latest", "*", "", "^1.0", "~1.0", ">=1.0"})
_STAGE_ARTIFACTS = (
    ("analysis.json", "analysis_digest"),
    ("plan.json", "plan_digest"),
    ("bundle.json", "bundle_digest"),
    ("validation.json", "validation_digest"),
)
_REQUIRED_COVERAGE = frozenset(
    {
        "safe_transform",
        "unsupported_semantics",
        "malformed_input",
        "cross_file_refs",
        "extension_metadata",
        "validator_failure",
        "replay",
        "source_redaction",
    }
)


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _normalize(obj: Any) -> Any:
    if isinstance(obj, str):
        return _nfc(obj)
    if isinstance(obj, dict):
        return {_nfc(str(key)): _normalize(item) for key, item in sorted(obj.items(), key=lambda x: str(x[0]))}
    if isinstance(obj, list):
        return [_normalize(item) for item in obj]
    return obj


def canonical_json(obj: Any) -> bytes:
    return json.dumps(_normalize(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def artifact_digest(artifact: dict[str, Any], digest_field: str) -> str:
    body = {key: value for key, value in artifact.items() if key != digest_field}
    return sha256_hex(canonical_json(body))


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _read_digest(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


@pytest.fixture(scope="module")
def corpus_manifest() -> dict[str, Any]:
    return _load_json(_MANIFEST_PATH)


@pytest.fixture(scope="module")
def unsafe_harness() -> dict[str, Any]:
    return _load_json(_UNSAFE_HARNESS_PATH)


@pytest.mark.issue(168)
class TestMigrationProfiles:
    @pytest.mark.parametrize(
        "filename",
        [
            "docs_myst_to_mdx_baseline.json",
            "api_spec_openapi_3_0_to_3_1_safe.json",
        ],
    )
    def test_profile_files_exist_and_match_adr(self, filename: str) -> None:
        path = _PROFILE_DIR / filename
        assert path.is_file(), f"missing profile fixture {path}"
        profile = _load_json(path)

        assert profile["schema_version"] == "migration-profile/v1"
        root_keys = set(profile)
        assert _REQUIRED_PROFILE_FIELDS <= root_keys
        assert root_keys - _REQUIRED_PROFILE_FIELDS <= _ALLOWED_OPTIONAL_PROFILE_FIELDS
        assert not (root_keys & _FORBIDDEN_ROOT_PROFILE_FIELDS)

        for side in ("source", "target"):
            kind_version = profile[side]
            assert isinstance(kind_version, dict)
            assert kind_version.get("version") not in _FLOATING_TOKENS
            assert "latest" not in str(kind_version.get("version", "")).lower()

        vocab = profile["feature_vocabulary"]
        for bucket in ("supported", "unsupported"):
            for entry in vocab[bucket]:
                assert entry["class"] in _FEATURE_CLASSES

        for tool in (profile["transformer"], profile["validator"]):
            assert set(tool) == {"name", "version", "digest"}
            assert len(tool["digest"]) == 64

        computed = artifact_digest({k: v for k, v in profile.items() if k != "profile_digest"}, "profile_digest")
        assert profile["profile_digest"] == computed

    def test_myst_profile_matches_adr_example_a(self) -> None:
        profile = _load_json(_PROFILE_DIR / "docs_myst_to_mdx_baseline.json")
        assert profile["profile_id"] == "docs/myst-to-mdx-baseline"
        assert profile["source"] == {"kind": "myst-markdown", "version": "1.3.0"}
        assert profile["target"] == {"kind": "mdx", "version": "3.0.0"}
        assert profile["compatibility_policy"]["policy_id"] == "docs-mdx-baseline-v1"

    def test_openapi_profile_matches_adr_example_b(self) -> None:
        profile = _load_json(_PROFILE_DIR / "api_spec_openapi_3_0_to_3_1_safe.json")
        assert profile["profile_id"] == "api-spec/openapi-3-0-to-3-1-safe"
        assert profile["source"] == {"kind": "openapi", "version": "3.0.3"}
        assert profile["target"] == {"kind": "openapi", "version": "3.1.0"}
        assert profile["compatibility_policy"]["policy_id"] == "openapi-client-server-v1"


@pytest.mark.issue(168)
class TestMigrationCorpusManifest:
    def test_manifest_lists_required_coverage(self, corpus_manifest: dict[str, Any]) -> None:
        assert corpus_manifest["version"] == 1
        assert corpus_manifest["schema"] == "orrery/migration-corpus/v1"
        covered: set[str] = set()
        for case in corpus_manifest["cases"]:
            covered.update(case["coverage"])
        assert _REQUIRED_COVERAGE <= covered

    def test_every_case_has_source_and_golden_stages(self, corpus_manifest: dict[str, Any]) -> None:
        for entry in corpus_manifest["cases"]:
            case_id = entry["case_id"]
            case_dir = _CORPUS_ROOT / "cases" / case_id
            assert (case_dir / "case.json").is_file()
            assert (case_dir / "source").is_dir()
            assert list((case_dir / "source").iterdir()), f"{case_id} has empty source/"
            assert (case_dir / "source_manifest.json").is_file()

            stages = case_dir / "stages"
            for artifact_name, digest_field in _STAGE_ARTIFACTS:
                artifact_path = stages / artifact_name
                digest_path = stages / f"{artifact_name}.digest"
                assert artifact_path.is_file(), f"{case_id} missing {artifact_name}"
                assert digest_path.is_file(), f"{case_id} missing golden digest for {artifact_name}"
                artifact = _load_json(artifact_path)
                golden = _read_digest(digest_path)
                assert artifact[digest_field] == golden
                assert artifact[digest_field] == artifact_digest(
                    {k: v for k, v in artifact.items() if k != digest_field},
                    digest_field,
                )

            replay_digest_path = stages / "replay_key.digest"
            assert replay_digest_path.is_file()
            meta = _load_json(case_dir / "case.json")
            replay_key = _read_digest(replay_digest_path)
            assert meta["stage_digests"]["replay_key"] == replay_key

    def test_source_manifest_digests_match_files(self, corpus_manifest: dict[str, Any]) -> None:
        for entry in corpus_manifest["cases"]:
            case_dir = _CORPUS_ROOT / "cases" / entry["case_id"]
            manifest = _load_json(case_dir / "source_manifest.json")
            for file_entry in manifest["files"]:
                rel = file_entry["path"]
                expected = sha256_hex((case_dir / "source" / rel).read_bytes())
                assert file_entry["digest"] == expected
            body = {"files": manifest["files"]}
            assert manifest["manifest_digest"] == sha256_hex(canonical_json(body))


@pytest.mark.issue(168)
class TestMigrationCorpusScenarios:
    def test_replay_case_documents_compatible_rerun(self, corpus_manifest: dict[str, Any]) -> None:
        case_dir = _CORPUS_ROOT / "cases" / "myst_replay_compatible"
        replay = _load_json(case_dir / "replay.json")
        stages = _load_json(case_dir / "stages" / "validation.json")
        assert replay["compatible"] is True
        assert replay["replay_key"] == _read_digest(case_dir / "stages" / "replay_key.digest")
        assert replay["reused_digest"] == stages["validation_digest"]

    def test_source_redaction_receipt_omits_private_bytes(self, corpus_manifest: dict[str, Any]) -> None:
        del corpus_manifest
        case_dir = _CORPUS_ROOT / "cases" / "myst_source_redaction"
        receipt = _load_json(case_dir / "receipt.json")
        assertion = _load_json(case_dir / "redaction_assert.json")

        assert assertion["source_byte_leak"] is False
        assert not assertion["forbidden_present"]
        raw = json.dumps(receipt)
        assert "CUSTOMER-SECRET" not in raw
        for forbidden in assertion["receipt_excludes_by_default"]:
            assert forbidden not in receipt

        computed = artifact_digest(
            {k: v for k, v in receipt.items() if k != "receipt_digest"},
            "receipt_digest",
        )
        assert receipt["receipt_digest"] == computed

    def test_validator_failure_case_reports_not_passed(self, corpus_manifest: dict[str, Any]) -> None:
        del corpus_manifest
        validation = _load_json(_CORPUS_ROOT / "cases" / "openapi_validator_failure" / "stages" / "validation.json")
        assert validation["passed"] is False
        breaking = [f for f in validation["findings"] if f.get("severity") == "breaking"]
        assert breaking

    def test_unsafe_harness_indexes_edge_cases(self, unsafe_harness: dict[str, Any]) -> None:
        assert unsafe_harness["version"] == 1
        blocked = {item["case_id"] for item in unsafe_harness["cases"] if item["expect_block"]}
        assert "openapi_validator_failure" in blocked
        assert "myst_malformed_directive" in blocked
