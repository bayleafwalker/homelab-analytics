from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class SecretReference:
    secret_name: str
    secret_key: str


class SecretResolver(Protocol):
    def resolve(self, secret_ref: SecretReference) -> str:
        """Return the secret value for *secret_ref* or raise KeyError."""


class EnvironmentSecretResolver:
    """Resolve secret references from environment variables.

    Variables are looked up using the pattern:
    ``HOMELAB_ANALYTICS_SECRET__<SECRET_NAME>__<SECRET_KEY>`` where both
    name and key are normalized to uppercase and non-alphanumeric characters
    become underscores.
    """

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ or os.environ

    def resolve(self, secret_ref: SecretReference) -> str:
        env_name = build_secret_env_var_name(
            secret_ref.secret_name,
            secret_ref.secret_key,
        )
        try:
            return self._environ[env_name]
        except KeyError as exc:
            raise KeyError(
                "Missing secret reference: "
                f"{secret_ref.secret_name}/{secret_ref.secret_key} "
                f"(expected env var {env_name})"
            ) from exc


def build_secret_env_var_name(secret_name: str, secret_key: str) -> str:
    return (
        "HOMELAB_ANALYTICS_SECRET__"
        f"{_normalize_secret_part(secret_name)}__"
        f"{_normalize_secret_part(secret_key)}"
    )


def _normalize_secret_part(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().upper()).strip("_")
    if not normalized:
        raise ValueError("Secret name and key must contain at least one alphanumeric character.")
    return normalized
