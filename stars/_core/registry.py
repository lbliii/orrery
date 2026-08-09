"""Loading and registration for built-in Star packages."""

from __future__ import annotations

import importlib
import importlib.resources
import tomllib
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

from .definition import StarDefinition, StarManifestError


def load_star_definition(path: str | Path) -> StarDefinition:
    """Load and validate a ``star.toml`` file from the filesystem."""
    manifest_path = Path(path)
    try:
        with manifest_path.open("rb") as manifest_file:
            decoded = tomllib.load(manifest_file)
    except FileNotFoundError as error:
        raise StarManifestError(f"Star manifest not found: {manifest_path}") from error
    except tomllib.TOMLDecodeError as error:
        raise StarManifestError(f"Invalid TOML in {manifest_path}: {error}") from error
    return StarDefinition.from_manifest(decoded)


def load_builtin_star_definition(package: str | ModuleType) -> StarDefinition:
    """Load the ``star.toml`` resource bundled with an importable package."""
    module = importlib.import_module(package) if isinstance(package, str) else package
    resource = importlib.resources.files(module).joinpath("star.toml")
    try:
        with resource.open("rb") as manifest_file:
            decoded = tomllib.load(manifest_file)
    except FileNotFoundError as error:
        raise StarManifestError(
            f"Star manifest not found in package {module.__name__!r}"
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise StarManifestError(f"Invalid TOML in package {module.__name__!r}: {error}") from error
    return StarDefinition.from_manifest(decoded)


class StarRegistry:
    """An explicit registry of validated built-in Star definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, StarDefinition] = {}

    def register(self, definition: StarDefinition) -> StarDefinition:
        """Register a definition, rejecting duplicate public names."""
        if definition.name in self._definitions:
            raise StarManifestError(f"Star already registered: {definition.name}")
        self._definitions[definition.name] = definition
        return definition

    def register_builtin(self, package: str | ModuleType) -> StarDefinition:
        """Load a package's bundled manifest and register its definition."""
        return self.register(load_builtin_star_definition(package))

    def get(self, name: str) -> StarDefinition:
        """Return a registered Star by its public name."""
        try:
            return self._definitions[name]
        except KeyError as error:
            raise KeyError(f"No Star registered with name {name!r}") from error

    def definitions(self) -> tuple[StarDefinition, ...]:
        """Return registrations in stable public-name order."""
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    def __contains__(self, name: object) -> bool:
        return name in self._definitions

    def __iter__(self) -> Iterator[StarDefinition]:
        return iter(self.definitions())
