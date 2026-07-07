"""Pack compatibility verification.

The ``PackCompatibilityChecker`` runs the checks that must pass before
a pack can be activated or upgraded:

- ``requires_platform_version`` — the pack's constraint must accept the
  current platform version.
- ``dependencies`` — each declared dependency must be present in the
  installed-packs mapping; if the dependency string carries a version
  constraint, the installed dependency version must satisfy it.
- ``publication_relations`` — every publication key the pack advertises
  must exist in the platform's known-publication set. Unknown
  publication keys are recorded as warnings so a pack can be activated
  in a staged environment where the publication is not yet materialized
  but the operator has decided to trust the pack.

The checker is HTTP-agnostic: it returns a ``CompatibilityCheck`` whose
``issues`` names blocking failures and whose ``warnings`` names
non-blocking concerns. Callers translate a non-empty ``issues`` set
into an activation refusal.
"""

from __future__ import annotations

from typing import Mapping

from packages.adapters.contracts import (
    AdapterPack,
    CompatibilityCheck,
    PackManifest,
)


def _parse_version(version: str) -> tuple[int, ...]:
    core = version.split("+", 1)[0].split("-", 1)[0].strip()
    if not core:
        return (0,)
    parts = core.split(".")
    parsed: list[int] = []
    for part in parts:
        try:
            parsed.append(int(part))
        except ValueError:
            parsed.append(0)
    return tuple(parsed)


_COMPARATORS = (">=", "<=", "==", ">", "<")


def _split_dependency(dep: str) -> tuple[str, str]:
    """Split ``pack_key`` or ``pack_key>=1.0`` into (pack_key, constraint)."""
    stripped = dep.strip()
    for op in _COMPARATORS:
        idx = stripped.find(op)
        if idx > 0:
            return stripped[:idx].strip(), stripped[idx:].strip()
    return stripped, ""


def satisfies_constraint(version: str, constraint: str) -> bool:
    """Return True if ``version`` satisfies ``constraint``.

    Empty constraint matches any version. Multiple clauses can be
    comma-separated (all must hold). A clause without a comparator is
    treated as an exact match. Only the numeric release segment is
    compared; pre-release and build metadata are ignored.
    """
    if not constraint or not constraint.strip():
        return True
    v = _parse_version(version)
    for raw_clause in constraint.split(","):
        clause = raw_clause.strip()
        if not clause:
            continue
        matched_op: str | None = None
        for op in _COMPARATORS:
            if clause.startswith(op):
                matched_op = op
                break
        target_str = clause[len(matched_op):].strip() if matched_op else clause
        t = _parse_version(target_str)
        if matched_op is None:
            if v != t:
                return False
        elif matched_op == "==":
            if v != t:
                return False
        elif matched_op == ">=":
            if v < t:
                return False
        elif matched_op == "<=":
            if v > t:
                return False
        elif matched_op == ">":
            if v <= t:
                return False
        elif matched_op == "<":
            if v >= t:
                return False
    return True


class PackCompatibilityChecker:
    """Verify a pack against the current platform and installed packs.

    Parameters
    ----------
    platform_version:
        Current platform release version, e.g. ``"0.1.5"``.
    installed_packs:
        Mapping of ``pack_key`` → ``PackManifest`` for packs already
        installed. Used to verify declared dependencies.
    known_publication_keys:
        Set of publication keys the platform knows about. Publication
        relations advertised by the pack that fall outside this set are
        surfaced as warnings.
    """

    def __init__(
        self,
        *,
        platform_version: str,
        installed_packs: Mapping[str, PackManifest],
        known_publication_keys: frozenset[str] | set[str] | tuple[str, ...] = (),
    ) -> None:
        self._platform_version = platform_version
        self._installed_packs = dict(installed_packs)
        self._known_publications = frozenset(known_publication_keys)

    def check(self, pack: PackManifest | AdapterPack) -> CompatibilityCheck:
        manifest = pack.to_pack_manifest() if isinstance(pack, AdapterPack) else pack
        issues: list[str] = []
        warnings: list[str] = []

        if manifest.requires_platform_version and not satisfies_constraint(
            self._platform_version, manifest.requires_platform_version
        ):
            issues.append(
                f"pack requires platform {manifest.requires_platform_version}; "
                f"running {self._platform_version}"
            )

        for dep in manifest.dependencies:
            dep_key, dep_constraint = _split_dependency(dep)
            if not dep_key:
                continue
            installed = self._installed_packs.get(dep_key)
            if installed is None:
                issues.append(f"missing dependency: {dep_key}")
                continue
            if dep_constraint and not satisfies_constraint(installed.version, dep_constraint):
                issues.append(
                    f"dependency {dep_key} {installed.version} does not satisfy {dep_constraint}"
                )

        for publication_key in manifest.publication_relations:
            if self._known_publications and publication_key not in self._known_publications:
                warnings.append(f"unknown publication key: {publication_key}")

        return CompatibilityCheck(
            is_compatible=not issues,
            issues=tuple(issues),
            warnings=tuple(warnings),
        )


__all__ = ["PackCompatibilityChecker", "satisfies_constraint"]
