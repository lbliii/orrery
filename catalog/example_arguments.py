"""Corpus-backed example tool arguments for discovery (#392).

Agents calling allowlist-gated stars get copy-pasteable happy-path arguments
from the publish corpus without reading repo fixtures or test files.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from chirp.skill.smoke import CorpusPrompt

from stars._core.corpus import load_publish_corpus
from stars.builtins import builtin_registry

from .coverage import CoverageAllowlist
from .star_page import (
    _arguments_validate,
    _input_schema,
    _required_properties,
    load_tool_contracts,
)


def example_arguments_for_tools(
    star_name: str,
    tools: tuple[str, ...] | list[str],
) -> dict[str, dict[str, object]]:
    """Map each tool name to corpus-backed example arguments."""
    if not tools:
        return {}
    corpus = _load_corpus(star_name)
    contracts = load_tool_contracts(star_name)
    return {
        tool: _example_for_tool(tool, corpus, contracts.get(tool))
        for tool in tools
    }


def example_arguments_for_coverage(
    spec: CoverageAllowlist,
    *,
    params: Mapping[str, str],
    allowed: bool,
    allowed_values: list[str] | None = None,
) -> dict[str, dict[str, object]]:
    """Build ``example_arguments`` for a coverage_check result."""
    contracts = load_tool_contracts(spec.star)
    tool = _coverage_tool(spec, contracts)
    if tool is None:
        return {}
    example = _example_for_tool(tool, _load_corpus(spec.star), contracts.get(tool))
    override = _coverage_param_overrides(spec, params, allowed, allowed_values)
    if override:
        example = {**example, **override}
    contract = contracts.get(tool)
    schema = _input_schema(contract)
    filtered = _filter_to_schema(example, schema)
    if schema and not _arguments_validate(filtered, schema):
        if not _required_properties(schema) and _arguments_validate({}, schema):
            filtered = {}
        else:
            filtered = _filter_to_schema(
                _example_for_tool(tool, _load_corpus(spec.star), contract),
                schema,
            )
    return {tool: filtered}


def _load_corpus(star_name: str) -> tuple[CorpusPrompt, ...]:
    try:
        definition = builtin_registry().get(star_name)
    except KeyError:
        return ()
    try:
        return load_publish_corpus(definition.publish_corpus)
    except Exception:
        return ()


def _example_for_tool(
    tool: str,
    corpus: tuple[CorpusPrompt, ...],
    contract: dict[str, Any] | None,
) -> dict[str, object]:
    """First corpus prompt for ``tool`` that validates; else ``{}`` when optional."""
    schema = _input_schema(contract)
    for prompt in corpus:
        if prompt.tool != tool:
            continue
        raw = prompt.arguments
        if not isinstance(raw, dict):
            continue
        filtered = _filter_to_schema(dict(raw), schema)
        if schema and not _arguments_validate(filtered, schema):
            continue
        return filtered
    if not _required_properties(schema) and _arguments_validate({}, schema):
        return {}
    return {}


def _filter_to_schema(arguments: dict[str, object], schema: dict[str, Any]) -> dict[str, object]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return dict(arguments)
    return {key: value for key, value in arguments.items() if key in properties}


def _coverage_tool(
    spec: CoverageAllowlist,
    contracts: dict[str, dict[str, Any]],
) -> str | None:
    matches: list[str] = []
    for tool, contract in contracts.items():
        properties = _input_schema(contract).get("properties")
        if isinstance(properties, dict) and spec.check_param in properties:
            matches.append(tool)
    if not matches:
        return next(iter(contracts), None)
    for preferred in ("get", "run", "fetch", "answer", "observe"):
        if preferred in matches:
            return preferred
    return matches[0]


def _coverage_param_overrides(
    spec: CoverageAllowlist,
    params: Mapping[str, str],
    allowed: bool,
    allowed_values: list[str] | None,
) -> dict[str, str]:
    if allowed:
        raw = params.get(spec.check_param)
        if raw is None and spec.check_param == "license_id":
            raw = params.get("id")
        if raw is not None and str(raw).strip():
            overrides = {spec.check_param: str(raw).strip()}
        else:
            return {}
    elif allowed_values:
        overrides = {spec.check_param: allowed_values[0]}
    else:
        return {}

    if spec.secondary_param:
        sec_raw = params.get(spec.secondary_param)
        if sec_raw is not None and str(sec_raw).strip():
            overrides[spec.secondary_param] = str(sec_raw).strip()
    return overrides
