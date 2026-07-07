"""Adapter secret resolution.

Adapters and renderers declare their credential needs on their manifests
(``AdapterManifest.credential_requirements``). This package resolves
those names to concrete secret values through a pluggable
``SecretResolver`` protocol so that the resolution backend — process
environment, a mounted secrets directory, or the control-plane store —
is not baked into adapter code.

Callers compose a resolver (usually a ``ChainedSecretResolver`` over
the concrete backends they want) and pass it to
``resolve_manifest_credentials`` to get a name → value mapping. A
missing required secret raises ``MissingSecretError`` with the offending
names so the caller can translate to a typed diagnostic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol, runtime_checkable


@runtime_checkable
class SecretResolver(Protocol):
    """Look up a secret by declared name.

    Return ``None`` when the resolver does not know about the name;
    return the string value when it does. Do not raise for a missing
    name — chaining relies on ``None`` to fall through to the next
    resolver.
    """

    def resolve(self, name: str) -> str | None:
        ...  # pragma: no cover


class EnvSecretResolver:
    """Resolve secrets from a process-environment-shaped mapping.

    Defaults to ``os.environ``; tests may pass a dict directly.
    """

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = env if env is not None else os.environ

    def resolve(self, name: str) -> str | None:
        value = self._env.get(name)
        if value is None or value == "":
            return None
        return value


class FileSecretResolver:
    """Resolve secrets from a directory of secret files.

    Each secret is a file whose name matches the declared secret name;
    the file contents (stripped of trailing whitespace) are the value.
    This mirrors the shape of Docker and Kubernetes secret mounts, where
    each key becomes a file under a mounted directory.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def resolve(self, name: str) -> str | None:
        candidate = self._root / name
        if not candidate.is_file():
            return None
        try:
            content = candidate.read_text().rstrip("\n").rstrip()
        except OSError:
            return None
        return content or None


class ControlPlaneSecretResolver:
    """Resolve secrets through a control-plane lookup callable.

    The callable receives a secret name and returns the string value or
    ``None``. Concrete integrations wire the callable to a
    ``ControlPlaneStore`` accessor (or an equivalent). Keeping this
    resolver behind a callable avoids coupling this package to a
    specific store table shape.
    """

    def __init__(self, lookup: Callable[[str], str | None]) -> None:
        self._lookup = lookup

    def resolve(self, name: str) -> str | None:
        value = self._lookup(name)
        if not value:
            return None
        return value


class ChainedSecretResolver:
    """Compose resolvers in priority order.

    The first resolver returning a non-``None`` value wins. A caller
    that wants control-plane values to override file mounts, which in
    turn override process env, chains them in that order.
    """

    def __init__(self, resolvers: Iterable[SecretResolver]) -> None:
        self._resolvers = tuple(resolvers)

    def resolve(self, name: str) -> str | None:
        for resolver in self._resolvers:
            value = resolver.resolve(name)
            if value is not None:
                return value
        return None


class MissingSecretError(RuntimeError):
    """Required credential names could not be resolved.

    ``missing`` names the unresolved secrets. Callers translate this
    into an adapter-activation-refused diagnostic without leaking any
    partial values that were resolved.
    """

    def __init__(self, missing: tuple[str, ...]) -> None:
        joined = ", ".join(missing)
        super().__init__(f"missing required secrets: {joined}")
        self.missing = missing


@dataclass(frozen=True)
class _ManifestLike:
    credential_requirements: tuple[str, ...]


def resolve_manifest_credentials(
    manifest_or_requirements: object,
    resolver: SecretResolver,
    *,
    optional: Iterable[str] = (),
) -> dict[str, str]:
    """Resolve the credentials declared on an adapter/renderer manifest.

    ``manifest_or_requirements`` may be any object with a
    ``credential_requirements`` attribute (typically an
    ``AdapterManifest``) or an iterable of names. Names listed in
    ``optional`` are omitted from the missing set when unresolved.
    """
    if hasattr(manifest_or_requirements, "credential_requirements"):
        requirements = tuple(manifest_or_requirements.credential_requirements)
    else:
        requirements = tuple(manifest_or_requirements)  # type: ignore[arg-type]

    optional_set = set(optional)
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for name in requirements:
        value = resolver.resolve(name)
        if value is not None:
            resolved[name] = value
        elif name not in optional_set:
            missing.append(name)
    if missing:
        raise MissingSecretError(tuple(missing))
    return resolved


__all__ = [
    "ChainedSecretResolver",
    "ControlPlaneSecretResolver",
    "EnvSecretResolver",
    "FileSecretResolver",
    "MissingSecretError",
    "SecretResolver",
    "resolve_manifest_credentials",
]
