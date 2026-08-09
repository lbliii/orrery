"""Load and validate per-star publish corpora (L1)."""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Mapping
from typing import Any

from chirp.skill.smoke import CorpusPrompt

from .definition import StarDefinition, StarManifestError


class StarCorpusError(StarManifestError):
    """A Star's publish corpus is missing, empty, or not a CorpusPrompt tuple."""


def load_publish_corpus(reference: str) -> tuple[CorpusPrompt, ...]:
    """Import ``module:attribute`` and return a non-mutated CorpusPrompt tuple.

    Raises :class:`StarCorpusError` when the reference cannot be loaded or does
    not resolve to a sequence of :class:`~chirp.skill.smoke.CorpusPrompt`.
    """
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise StarCorpusError(
            f"publish corpus must be a module:attribute reference, got {reference!r}"
        )
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise StarCorpusError(f"cannot import publish corpus module {module_name!r}") from error
    try:
        value = getattr(module, attribute)
    except AttributeError as error:
        raise StarCorpusError(
            f"publish corpus attribute {attribute!r} missing on {module_name!r}"
        ) from error
    return _as_corpus_tuple(value, reference=reference)


def require_nonempty_corpus(definition: StarDefinition) -> tuple[CorpusPrompt, ...]:
    """Load ``definition.publish_corpus`` and require at least one CorpusPrompt."""
    corpus = load_publish_corpus(definition.publish_corpus)
    if not corpus:
        raise StarCorpusError(
            f"public star {definition.name!r} must ship a non-empty CORPUS "
            f"({definition.publish_corpus})"
        )
    return corpus


def corpus_ok_by_star(definitions: Iterable[StarDefinition]) -> dict[str, bool]:
    """Return ``{star_name: True}`` when the declared CORPUS loads and is non-empty."""
    result: dict[str, bool] = {}
    for definition in definitions:
        try:
            require_nonempty_corpus(definition)
        except StarCorpusError:
            result[definition.name] = False
        else:
            result[definition.name] = True
    return result


def validate_public_star_corpora(definitions: Iterable[StarDefinition]) -> None:
    """Raise :class:`StarCorpusError` if any public star lacks a non-empty CORPUS."""
    failures: list[str] = []
    for definition in definitions:
        try:
            require_nonempty_corpus(definition)
        except StarCorpusError as error:
            failures.append(str(error))
    if failures:
        joined = "; ".join(failures)
        raise StarCorpusError(f"L1 corpus gate failed: {joined}")


def _as_corpus_tuple(value: Any, *, reference: str) -> tuple[CorpusPrompt, ...]:
    if isinstance(value, CorpusPrompt):
        return (value,)
    if isinstance(value, str):
        raise StarCorpusError(
            f"{reference} must be a sequence of CorpusPrompt, got str"
        )
    if isinstance(value, Mapping):
        raise StarCorpusError(
            f"{reference} must be a sequence of CorpusPrompt, not a mapping"
        )
    try:
        items = tuple(value)
    except TypeError as error:
        raise StarCorpusError(f"{reference} must be a sequence of CorpusPrompt") from error
    for index, item in enumerate(items):
        if not isinstance(item, CorpusPrompt):
            raise StarCorpusError(
                f"{reference}[{index}] must be CorpusPrompt, got {type(item).__name__}"
            )
    return items
