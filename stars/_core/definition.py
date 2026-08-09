"""The portable manifest contract for a Star capability package."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .execution import ManagedCPUExecutionPolicy, ManagedCPUExecutionPolicyError, ManagedCPUWorkload


class StarManifestError(ValueError):
    """A ``star.toml`` document does not satisfy the Star manifest contract."""


@dataclass(frozen=True, slots=True)
class StarDefinition:
    """Validated identity, pricing, runtime, policy, receipt, and publish metadata.

    This is deliberately framework-neutral: ``skill_factory`` and ``corpus``
    are import references rather than imported objects, and the publisher key
    is an environment-variable reference rather than a secret value.
    """

    name: str
    version: str
    description: str
    publisher: str
    publisher_key_id_env: str
    direct_mcp_path: str
    price_per_call: Decimal
    price_unit: str
    price_currency: str
    python_package: str
    skill_factory: str
    execution_mode: str
    managed_cpu_workload: ManagedCPUWorkload | None
    allowed_egress: tuple[str, ...]
    freshness: str
    redirects: str
    max_response_bytes: int
    receipt_schema_version: str
    receipt_algorithm: str
    publish_corpus: str
    tools: tuple[str, ...] = ()

    @property
    def endpoint_path(self) -> str:
        """Compatibility-friendly name for the canonical direct MCP path."""
        return self.direct_mcp_path

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, Any]) -> StarDefinition:
        """Build a definition from a decoded canonical nested ``star.toml``."""
        star = _require_table(manifest, "star")
        pricing = _require_table(manifest, "pricing")
        runtime = _require_table(manifest, "runtime")
        policy = _require_table(manifest, "policy")
        receipt = _require_table(manifest, "receipt")
        publish = _require_table(manifest, "publish")
        execution_mode = _optional_nonempty_string(
            runtime, "runtime", "execution_mode", "direct-mcp"
        )
        if execution_mode not in {"direct-mcp", "managed-cpu"}:
            raise StarManifestError("runtime.execution_mode must be direct-mcp or managed-cpu")
        allowed_egress = _require_string_list(policy, "policy", "allowed_egress")

        definition = cls(
            name=_require_nonempty_string(star, "star", "name"),
            version=_require_nonempty_string(star, "star", "version"),
            description=_require_nonempty_string(star, "star", "description"),
            publisher=_require_nonempty_string(star, "star", "publisher"),
            publisher_key_id_env=_require_nonempty_string(star, "star", "publisher_key_id_env"),
            direct_mcp_path=_require_direct_mcp_path(star),
            price_per_call=_require_non_negative_decimal(pricing, "price_per_call"),
            price_unit=_require_nonempty_string(pricing, "pricing", "unit"),
            price_currency=_require_nonempty_string(pricing, "pricing", "currency"),
            python_package=_require_module_reference(runtime, "runtime", "python_package"),
            skill_factory=_require_attribute_reference(runtime, "runtime", "skill_factory"),
            execution_mode=execution_mode,
            managed_cpu_workload=_managed_cpu_workload(manifest, execution_mode, allowed_egress),
            allowed_egress=allowed_egress,
            freshness=_require_nonempty_string(policy, "policy", "freshness"),
            redirects=_require_nonempty_string(policy, "policy", "redirects"),
            max_response_bytes=_require_positive_integer(policy, "max_response_bytes"),
            receipt_schema_version=_require_nonempty_string(receipt, "receipt", "schema_version"),
            receipt_algorithm=_require_nonempty_string(receipt, "receipt", "algorithm"),
            publish_corpus=_require_attribute_reference(publish, "publish", "corpus"),
            tools=_optional_string_list(star, "star", "tools"),
        )
        _validate_unique(definition.allowed_egress, "policy.allowed_egress")
        _validate_unique(definition.tools, "star.tools")
        return definition


# The on-disk manifest is the authoritative definition model.
StarManifest = StarDefinition


def _require_table(manifest: Mapping[str, Any], table: str) -> Mapping[str, Any]:
    value = manifest.get(table)
    if not isinstance(value, Mapping):
        raise StarManifestError(f"manifest must contain a [{table}] table")
    return value


def _require_nonempty_string(values: Mapping[str, Any], table: str, field: str) -> str:
    value = values.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StarManifestError(f"{table}.{field} must be a non-empty string")
    return value


def _optional_nonempty_string(
    values: Mapping[str, Any], table: str, field: str, default: str
) -> str:
    if field not in values:
        return default
    return _require_nonempty_string(values, table, field)


def _require_direct_mcp_path(values: Mapping[str, Any]) -> str:
    path = _require_nonempty_string(values, "star", "direct_mcp_path")
    if not path.startswith("/"):
        raise StarManifestError("star.direct_mcp_path must start with '/'")
    if "?" in path or "#" in path:
        raise StarManifestError("star.direct_mcp_path must not contain a query or fragment")
    return path


def _require_non_negative_decimal(values: Mapping[str, Any], field: str) -> Decimal:
    value = values.get(field)
    if not isinstance(value, str):
        raise StarManifestError(f"pricing.{field} must be a non-negative decimal string")
    try:
        decimal_value = Decimal(value)
    except InvalidOperation as error:
        raise StarManifestError(f"pricing.{field} must be a non-negative decimal string") from error
    if not decimal_value.is_finite() or decimal_value < 0:
        raise StarManifestError(f"pricing.{field} must be a non-negative decimal string")
    return decimal_value


def _require_positive_integer(values: Mapping[str, Any], field: str) -> int:
    value = values.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StarManifestError(f"policy.{field} must be a positive integer")
    return value


def _require_module_reference(values: Mapping[str, Any], table: str, field: str) -> str:
    reference = _require_nonempty_string(values, table, field)
    if ":" in reference:
        raise StarManifestError(f"{table}.{field} must be a dotted module reference")
    return reference


def _require_attribute_reference(values: Mapping[str, Any], table: str, field: str) -> str:
    reference = _require_nonempty_string(values, table, field)
    if ":" not in reference:
        raise StarManifestError(f"{table}.{field} must be a module:attribute reference")
    return reference


def _require_string_list(values: Mapping[str, Any], table: str, field: str) -> tuple[str, ...]:
    value = values.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise StarManifestError(f"{table}.{field} must be a list of non-empty strings")
    return tuple(value)


def _optional_string_list(values: Mapping[str, Any], table: str, field: str) -> tuple[str, ...]:
    if field not in values:
        return ()
    return _require_string_list(values, table, field)


def _managed_cpu_workload(
    manifest: Mapping[str, Any], execution_mode: str, allowed_egress: tuple[str, ...]
) -> ManagedCPUWorkload | None:
    configured = manifest.get("managed_cpu")
    if execution_mode != "managed-cpu":
        if configured is not None:
            raise StarManifestError("[managed_cpu] requires runtime.execution_mode = managed-cpu")
        return None
    if not isinstance(configured, Mapping):
        raise StarManifestError("managed-cpu Stars must contain a [managed_cpu] table")
    try:
        policy = ManagedCPUExecutionPolicy(
            cpu_millicores=_require_positive_integer(configured, "cpu_millicores"),
            memory_bytes=_require_positive_integer(configured, "memory_bytes"),
            wall_time_seconds=_require_positive_integer(configured, "wall_time_seconds"),
            max_input_bytes=_require_positive_integer(configured, "max_input_bytes"),
            max_output_bytes=_require_positive_integer(configured, "max_output_bytes"),
            allowed_egress=allowed_egress,
        )
        return ManagedCPUWorkload(
            image_digest=_require_nonempty_string(configured, "managed_cpu", "image_digest"),
            command=_require_string_list(configured, "managed_cpu", "command"),
            policy=policy,
        )
    except ManagedCPUExecutionPolicyError as error:
        raise StarManifestError(f"invalid managed_cpu policy: {error}") from error


def _validate_unique(values: tuple[str, ...], field: str) -> None:
    if len(set(values)) != len(values):
        raise StarManifestError(f"{field} must not contain duplicates")
