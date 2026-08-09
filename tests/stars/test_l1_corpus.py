"""L1: public stars must ship a non-empty CORPUS (#117)."""

from __future__ import annotations

import pytest
from chirp.skill.smoke import CorpusPrompt

from stars._core import StarCorpusError, require_nonempty_corpus, validate_public_star_corpora
from stars._core.corpus import load_publish_corpus
from stars.builtins import BUILTIN_STAR_PACKAGES, builtin_registry
from stars.html_to_pdf.corpus import CORPUS as PDF_CORPUS
from stars.source_watch.corpus import CORPUS as SOURCE_WATCH_CORPUS
from stars.world_time.corpus import CORPUS as WORLD_TIME_CORPUS
from tests.stars.helpers import assert_manifest_publish_corpus
from trust.oracle import configure_oracle, oracle_ok_for_record


@pytest.mark.issue(117)
class TestL1PublicStarCorpus:
    @pytest.mark.parametrize("package", BUILTIN_STAR_PACKAGES)
    def test_builtin_package_declares_and_loads_nonempty_corpus(self, package: str) -> None:
        short = package.rsplit(".", maxsplit=1)[-1]
        reference = assert_manifest_publish_corpus(short)
        corpus = load_publish_corpus(reference)
        assert len(corpus) >= 1
        assert all(isinstance(item, CorpusPrompt) for item in corpus)

    def test_dogfood_corpora_are_nonempty(self) -> None:
        assert len(PDF_CORPUS) >= 1
        assert len(WORLD_TIME_CORPUS) >= 1
        assert len(SOURCE_WATCH_CORPUS) >= 1

    def test_registry_validation_passes_for_builtins(self) -> None:
        validate_public_star_corpora(builtin_registry())

    def test_empty_corpus_fails_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import stars.world_time.corpus as world_time_corpus

        monkeypatch.setattr(world_time_corpus, "CORPUS", ())
        with pytest.raises(StarCorpusError, match="non-empty CORPUS"):
            require_nonempty_corpus(builtin_registry().get("orrery/world-time"))

    def test_missing_corpus_forces_oracle_not_ok(self) -> None:
        from catalog.models import ResolveRecord

        record = ResolveRecord(
            name="orrery/world-time",
            endpoint="mcp://orrery.lol/stars/world-time/mcp",
            content_digest="sha256:deadbeef",
            kind="star",
            visibility="public",
            version="0.1.0",
            description="test",
            key_id="k",
            oracle_ok=True,
            tools=("answer",),
        )
        configure_oracle(receipt=None, scores=None, corpus_ok={"orrery/world-time": False})
        assert oracle_ok_for_record(record) is False
        configure_oracle(receipt=None, scores=None, corpus_ok={})
