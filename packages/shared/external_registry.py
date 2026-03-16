from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import uuid4

from packages.pipelines.extension_registries import load_pipeline_registries
from packages.shared.extensions import load_extension_registry
from packages.shared.function_registry import load_function_registry
from packages.shared.secrets import (
    EnvironmentSecretResolver,
    SecretReference,
    SecretResolver,
)
from packages.storage.control_plane import ExternalRegistryStore
from packages.storage.external_registry_catalog import (
    ExtensionRegistryActivationRecord,
    ExtensionRegistryRevisionCreate,
    ExtensionRegistryRevisionRecord,
    ExtensionRegistrySourceRecord,
)

EXTERNAL_REGISTRY_MANIFEST_FILENAME = "homelab-analytics.registry.json"


@dataclass(frozen=True)
class ExtensionRegistryManifest:
    schema_version: int
    import_paths: tuple[str, ...]
    extension_modules: tuple[str, ...]
    function_modules: tuple[str, ...] = ()
    minimum_platform_version: str | None = None
    display_name: str | None = None
    homepage: str | None = None


@dataclass(frozen=True)
class ExtensionRegistrySyncResult:
    source: ExtensionRegistrySourceRecord
    revision: ExtensionRegistryRevisionRecord
    activation: ExtensionRegistryActivationRecord | None = None

    @property
    def passed(self) -> bool:
        return self.revision.sync_status == "validated"


@dataclass(frozen=True)
class ResolvedExtensionSettings:
    extension_paths: tuple[Path, ...]
    extension_modules: tuple[str, ...]
    function_modules: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedExternalRegistrySource:
    runtime_root: Path
    manifest_path: Path
    resolved_ref: str | None
    content_fingerprint: str | None


def load_extension_registry_manifest(root: Path) -> ExtensionRegistryManifest:
    manifest_path = root / EXTERNAL_REGISTRY_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "External registry manifest not found: "
            f"{manifest_path}"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return parse_extension_registry_manifest(payload)


def parse_extension_registry_manifest(payload: dict[str, object]) -> ExtensionRegistryManifest:
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, int):
        raise ValueError("External registry manifest requires integer schema_version.")
    if schema_version != 1:
        raise ValueError(
            f"Unsupported external registry manifest schema_version: {schema_version!r}"
        )

    import_paths = _normalize_string_list(payload.get("import_paths"), field_name="import_paths")
    extension_modules = _normalize_string_list(
        payload.get("extension_modules"),
        field_name="extension_modules",
    )
    function_modules = _normalize_string_list(
        payload.get("function_modules"),
        field_name="function_modules",
        required=False,
    )
    if not extension_modules and not function_modules:
        raise ValueError(
            "External registry manifest must declare extension_modules, function_modules, or both."
        )
    for import_path in import_paths:
        if Path(import_path).is_absolute():
            raise ValueError("External registry import_paths must be relative paths.")

    minimum_platform_version = _normalize_optional_string(
        payload.get("minimum_platform_version")
    )
    display_name = _normalize_optional_string(payload.get("display_name"))
    homepage = _normalize_optional_string(payload.get("homepage"))

    return ExtensionRegistryManifest(
        schema_version=schema_version,
        import_paths=tuple(import_paths or ["."]),
        extension_modules=tuple(extension_modules),
        function_modules=tuple(function_modules),
        minimum_platform_version=minimum_platform_version,
        display_name=display_name,
        homepage=homepage,
    )


def sync_extension_registry_source(
    store: ExternalRegistryStore,
    extension_registry_source_id: str,
    *,
    activate: bool = False,
    cache_root: Path | None = None,
    secret_resolver: SecretResolver | None = None,
    synchronized_at: datetime | None = None,
) -> ExtensionRegistrySyncResult:
    source = store.get_extension_registry_source(extension_registry_source_id)
    now = synchronized_at or datetime.now(UTC)
    source_root: Path | None = None
    manifest_path: Path | None = None
    resolved_ref: str | None = None

    try:
        if source.archived:
            raise ValueError(
                f"External registry source is archived: {source.extension_registry_source_id}"
            )
        if not source.enabled:
            raise ValueError(
                f"External registry source is disabled: {source.extension_registry_source_id}"
            )
        prepared_source = _prepare_external_registry_source(
            source,
            cache_root=cache_root,
            secret_resolver=secret_resolver,
        )
        source_root = prepared_source.runtime_root
        manifest_path = prepared_source.manifest_path
        resolved_ref = prepared_source.resolved_ref
        manifest = load_extension_registry_manifest(source_root)
        _validate_manifest_platform_compatibility(manifest)
        _validate_manifest_modules(source_root, manifest)

        revision = store.create_extension_registry_revision(
            ExtensionRegistryRevisionCreate(
                extension_registry_revision_id=f"extrev-{uuid4().hex}",
                extension_registry_source_id=source.extension_registry_source_id,
                resolved_ref=resolved_ref or str(source_root.resolve()),
                runtime_path=str(source_root.resolve()),
                manifest_path=str(manifest_path.resolve()),
                manifest_digest=_build_manifest_digest(manifest),
                manifest_version=manifest.schema_version,
                content_fingerprint=prepared_source.content_fingerprint,
                import_paths=manifest.import_paths,
                extension_modules=manifest.extension_modules,
                function_modules=manifest.function_modules,
                minimum_platform_version=manifest.minimum_platform_version,
                sync_status="validated",
                validation_error=None,
                created_at=now,
            )
        )
    except Exception as exc:
        revision = store.create_extension_registry_revision(
            ExtensionRegistryRevisionCreate(
                extension_registry_revision_id=f"extrev-{uuid4().hex}",
                extension_registry_source_id=source.extension_registry_source_id,
                resolved_ref=resolved_ref,
                runtime_path=(
                    str(source_root.resolve())
                    if source_root is not None and source_root.exists()
                    else None
                ),
                manifest_path=(
                    str(manifest_path.resolve())
                    if manifest_path is not None and manifest_path.exists()
                    else (str(manifest_path) if manifest_path is not None else None)
                ),
                sync_status="failed",
                validation_error=str(exc),
                created_at=now,
            )
        )
        return ExtensionRegistrySyncResult(
            source=source,
            revision=revision,
            activation=None,
        )

    activation_record = (
        store.activate_extension_registry_revision(
            extension_registry_source_id=source.extension_registry_source_id,
            extension_registry_revision_id=revision.extension_registry_revision_id,
            activated_at=now,
        )
        if activate
        else None
    )
    return ExtensionRegistrySyncResult(
        source=source,
        revision=revision,
        activation=activation_record,
    )


def resolve_active_extension_settings(
    store: ExternalRegistryStore,
    *,
    configured_paths: tuple[Path, ...] = (),
    configured_modules: tuple[str, ...] = (),
) -> ResolvedExtensionSettings:
    extension_paths = list(configured_paths)
    extension_modules = list(configured_modules)
    function_modules: list[str] = []

    for activation in store.list_extension_registry_activations():
        source = store.get_extension_registry_source(activation.extension_registry_source_id)
        if source.archived or not source.enabled:
            continue
        revision = store.get_extension_registry_revision(
            activation.extension_registry_revision_id
        )
        if revision.sync_status != "validated" or revision.runtime_path is None:
            continue
        runtime_root = Path(revision.runtime_path)
        for import_path in revision.import_paths or (".",):
            resolved_path = (
                Path(import_path)
                if Path(import_path).is_absolute()
                else (runtime_root / import_path)
            ).resolve()
            if resolved_path not in extension_paths:
                extension_paths.append(resolved_path)
        for module_name in revision.extension_modules:
            if module_name not in extension_modules:
                extension_modules.append(module_name)
        for module_name in revision.function_modules:
            if module_name not in function_modules:
                function_modules.append(module_name)

    return ResolvedExtensionSettings(
        extension_paths=tuple(extension_paths),
        extension_modules=tuple(extension_modules),
        function_modules=tuple(function_modules),
    )


def _prepare_external_registry_source(
    source: ExtensionRegistrySourceRecord,
    *,
    cache_root: Path | None,
    secret_resolver: SecretResolver | None,
) -> PreparedExternalRegistrySource:
    if source.source_kind == "path":
        source_root = _resolve_source_root(source)
        return PreparedExternalRegistrySource(
            runtime_root=source_root,
            manifest_path=source_root / EXTERNAL_REGISTRY_MANIFEST_FILENAME,
            resolved_ref=str(source_root.resolve()),
            content_fingerprint=_build_directory_fingerprint(source_root),
        )
    if source.source_kind == "git":
        if cache_root is None:
            raise ValueError(
                "Git-backed external registry sync requires a cache_root."
            )
        return _prepare_git_external_registry_source(
            source,
            cache_root=cache_root,
            secret_resolver=secret_resolver,
        )
    raise ValueError(
        f"Unsupported external registry source kind: {source.source_kind!r}"
    )


def _resolve_source_root(source: ExtensionRegistrySourceRecord) -> Path:
    root = Path(source.location)
    if source.subdirectory:
        root = root / source.subdirectory
    return root


def _normalize_string_list(
    value: object,
    *,
    field_name: str,
    required: bool = True,
) -> list[str]:
    if value is None:
        if required:
            raise ValueError(f"External registry manifest requires {field_name}.")
        return []
    if not isinstance(value, list):
        raise ValueError(f"External registry manifest field {field_name} must be a list.")
    normalized: list[str] = []
    for item in value:
        item_value = _normalize_optional_string(item)
        if item_value is None:
            raise ValueError(
                f"External registry manifest field {field_name} must not contain empty values."
            )
        normalized.append(item_value)
    return normalized


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("External registry manifest string fields must be strings.")
    normalized = value.strip()
    return normalized or None


def _build_manifest_digest(manifest: ExtensionRegistryManifest) -> str:
    payload = {
        "schema_version": manifest.schema_version,
        "import_paths": list(manifest.import_paths),
        "extension_modules": list(manifest.extension_modules),
        "function_modules": list(manifest.function_modules),
        "minimum_platform_version": manifest.minimum_platform_version,
        "display_name": manifest.display_name,
        "homepage": manifest.homepage,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _build_directory_fingerprint(root: Path) -> str:
    if not root.exists():
        raise FileNotFoundError(f"External registry source path does not exist: {root}")
    digest = hashlib.sha256()
    for path in sorted(
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file()
        and ".git" not in candidate.parts
        and "__pycache__" not in candidate.parts
    ):
        stat = path.stat()
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
    return digest.hexdigest()


def _validate_manifest_platform_compatibility(
    manifest: ExtensionRegistryManifest,
) -> None:
    if not manifest.minimum_platform_version:
        return
    current_version = _current_platform_version()
    if _parse_version_tuple(current_version) < _parse_version_tuple(
        manifest.minimum_platform_version
    ):
        raise ValueError(
            "External registry requires homelab-analytics>="
            f"{manifest.minimum_platform_version}, current runtime is {current_version}."
        )


def _validate_manifest_modules(
    source_root: Path,
    manifest: ExtensionRegistryManifest,
) -> None:
    extension_paths = tuple((source_root / import_path).resolve() for import_path in manifest.import_paths)
    if manifest.extension_modules:
        load_extension_registry(
            extension_paths=extension_paths,
            extension_modules=manifest.extension_modules,
        )
        load_pipeline_registries(
            extension_paths=extension_paths,
            extension_modules=manifest.extension_modules,
        )
    if manifest.function_modules:
        load_function_registry(
            extension_paths=extension_paths,
            function_modules=manifest.function_modules,
        )


def _current_platform_version() -> str:
    try:
        return version("homelab-analytics")
    except PackageNotFoundError:
        project_root = Path(__file__).resolve().parents[2]
        pyproject_path = project_root / "pyproject.toml"
        for line in pyproject_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("version = "):
                return line.split('"', 2)[1]
        return "0.0.0"


def _parse_version_tuple(value: str) -> tuple[int, ...]:
    parts = value.split(".")
    parsed: list[int] = []
    for part in parts:
        if not part.isdigit():
            raise ValueError(
                f"Unsupported semantic version value for external registry compatibility: {value!r}"
            )
        parsed.append(int(part))
    return tuple(parsed)


def _prepare_git_external_registry_source(
    source: ExtensionRegistrySourceRecord,
    *,
    cache_root: Path,
    secret_resolver: SecretResolver | None,
) -> PreparedExternalRegistrySource:
    source_cache_root = (
        cache_root
        / source.extension_registry_source_id
    ).resolve()
    source_cache_root.mkdir(parents=True, exist_ok=True)
    repo_root = source_cache_root / "repo"
    revisions_root = source_cache_root / "revisions"
    revisions_root.mkdir(parents=True, exist_ok=True)
    environment = _build_git_environment(
        source,
        secret_resolver=secret_resolver,
    )

    if repo_root.exists() and not (repo_root / ".git").exists():
        shutil.rmtree(repo_root)

    if not repo_root.exists():
        _run_git_command(
            (
                "git",
                "clone",
                "--no-checkout",
                source.location,
                str(repo_root),
            ),
            env=environment,
        )
    else:
        _run_git_command(
            (
                "git",
                "-C",
                str(repo_root),
                "remote",
                "set-url",
                "origin",
                source.location,
            ),
            env=environment,
        )

    _run_git_command(
        (
            "git",
            "-C",
            str(repo_root),
            "fetch",
            "--prune",
            "--tags",
            "origin",
        ),
        env=environment,
    )
    try:
        _run_git_command(
            (
                "git",
                "-C",
                str(repo_root),
                "remote",
                "set-head",
                "origin",
                "--auto",
            ),
            env=environment,
        )
    except ValueError:
        pass

    resolved_ref = _resolve_git_commit(
        repo_root,
        desired_ref=source.desired_ref,
        env=environment,
    )
    worktree_root = revisions_root / resolved_ref
    if worktree_root.exists():
        if not (worktree_root / ".git").exists():
            shutil.rmtree(worktree_root)
            _run_git_command(
                (
                    "git",
                    "-C",
                    str(repo_root),
                    "worktree",
                    "prune",
                ),
                env=environment,
            )
        else:
            current_head = _run_git_command(
                (
                    "git",
                    "-C",
                    str(worktree_root),
                    "rev-parse",
                    "HEAD",
                ),
                env=environment,
            )
            if current_head != resolved_ref:
                shutil.rmtree(worktree_root)
                _run_git_command(
                    (
                        "git",
                        "-C",
                        str(repo_root),
                        "worktree",
                        "prune",
                    ),
                    env=environment,
                )

    if not worktree_root.exists():
        _run_git_command(
            (
                "git",
                "-C",
                str(repo_root),
                "worktree",
                "add",
                "--detach",
                str(worktree_root),
                resolved_ref,
            ),
            env=environment,
        )

    runtime_root = worktree_root
    if source.subdirectory:
        runtime_root = worktree_root / source.subdirectory
    if not runtime_root.exists():
        raise FileNotFoundError(
            "External registry git source subdirectory does not exist: "
            f"{runtime_root}"
        )

    return PreparedExternalRegistrySource(
        runtime_root=runtime_root,
        manifest_path=runtime_root / EXTERNAL_REGISTRY_MANIFEST_FILENAME,
        resolved_ref=resolved_ref,
        content_fingerprint=resolved_ref,
    )


def _resolve_git_commit(
    repo_root: Path,
    *,
    desired_ref: str | None,
    env: dict[str, str],
) -> str:
    normalized_ref = desired_ref.strip() if desired_ref else ""
    if not normalized_ref:
        for candidate in ("refs/remotes/origin/HEAD", "HEAD"):
            try:
                return _run_git_command(
                    (
                        "git",
                        "-C",
                        str(repo_root),
                        "rev-parse",
                        "--verify",
                        f"{candidate}^{{commit}}",
                    ),
                    env=env,
                )
            except ValueError:
                continue
        raise ValueError(
            "Unable to resolve the default commit for the external registry Git source."
        )

    candidates = (
        normalized_ref,
        f"refs/remotes/origin/{normalized_ref}",
        f"origin/{normalized_ref}",
        f"refs/tags/{normalized_ref}",
    )
    for candidate in candidates:
        try:
            return _run_git_command(
                (
                    "git",
                    "-C",
                    str(repo_root),
                    "rev-parse",
                    "--verify",
                    f"{candidate}^{{commit}}",
                ),
                env=env,
            )
        except ValueError:
            continue
    raise ValueError(
        "Unable to resolve desired_ref for the external registry Git source: "
        f"{normalized_ref!r}"
    )


def _build_git_environment(
    source: ExtensionRegistrySourceRecord,
    *,
    secret_resolver: SecretResolver | None,
) -> dict[str, str]:
    environment = dict(os.environ)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    if source.auth_secret_name is None and source.auth_secret_key is None:
        return environment
    if not source.auth_secret_name or not source.auth_secret_key:
        raise ValueError(
            "External registry git auth requires both auth_secret_name and auth_secret_key."
        )
    if not source.location.startswith(("http://", "https://")):
        raise ValueError(
            "External registry git auth currently supports only http(s) repository URLs."
        )
    resolver = secret_resolver or EnvironmentSecretResolver()
    credential_value = resolver.resolve(
        SecretReference(
            secret_name=source.auth_secret_name,
            secret_key=source.auth_secret_key,
        )
    ).strip()
    if not credential_value:
        raise ValueError("External registry git auth secret resolved to an empty value.")
    authorization_value = _build_git_authorization_header(credential_value)
    return _append_git_config_environment(
        environment,
        key="http.extraHeader",
        value=authorization_value,
    )


def _build_git_authorization_header(credential_value: str) -> str:
    if ":" in credential_value:
        username, password = credential_value.split(":", 1)
    else:
        username, password = "x-access-token", credential_value
    if not username or not password:
        raise ValueError(
            "External registry git auth secret must contain a token or username:password."
        )
    encoded = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("ascii")
    return f"Authorization: Basic {encoded}"


def _append_git_config_environment(
    environment: dict[str, str],
    *,
    key: str,
    value: str,
) -> dict[str, str]:
    updated_environment = dict(environment)
    config_count = int(updated_environment.get("GIT_CONFIG_COUNT", "0"))
    updated_environment["GIT_CONFIG_COUNT"] = str(config_count + 1)
    updated_environment[f"GIT_CONFIG_KEY_{config_count}"] = key
    updated_environment[f"GIT_CONFIG_VALUE_{config_count}"] = value
    return updated_environment


def _run_git_command(
    command: tuple[str, ...],
    *,
    env: dict[str, str],
) -> str:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError as exc:
        raise ValueError("Git executable is not available in this environment.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "unknown git failure"
        raise ValueError(
            f"Git command failed ({' '.join(command)}): {detail}"
        ) from exc
    return completed.stdout.strip()
