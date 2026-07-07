"""Tests for PackCompatibilityChecker."""

from __future__ import annotations

from packages.adapters.contracts import (
    PACK_KIND_ADAPTER,
    PackManifest,
    TrustLevel,
)
from packages.adapters.pack_compatibility import (
    PackCompatibilityChecker,
    satisfies_constraint,
)


def _manifest(
    *,
    pack_key: str = "example",
    version: str = "1.0.0",
    requires_platform_version: str = "",
    dependencies: tuple[str, ...] = (),
    publication_relations: tuple[str, ...] = (),
) -> PackManifest:
    return PackManifest(
        pack_key=pack_key,
        display_name=pack_key,
        version=version,
        trust_level=TrustLevel.LOCAL,
        pack_kind=PACK_KIND_ADAPTER,
        requires_platform_version=requires_platform_version,
        dependencies=dependencies,
        publication_relations=publication_relations,
    )


def test_satisfies_constraint_empty_matches_any():
    assert satisfies_constraint("0.1.0", "") is True
    assert satisfies_constraint("99.0.0", "   ") is True


def test_satisfies_constraint_supports_common_operators():
    assert satisfies_constraint("0.2.0", ">=0.1.0") is True
    assert satisfies_constraint("0.0.9", ">=0.1.0") is False
    assert satisfies_constraint("0.1.0", "<=0.1.0") is True
    assert satisfies_constraint("1.0.0", "<1.0.0") is False
    assert satisfies_constraint("0.9.9", "<1.0.0") is True
    assert satisfies_constraint("1.2.3", "==1.2.3") is True


def test_satisfies_constraint_supports_comma_composition():
    assert satisfies_constraint("0.5.0", ">=0.1.0,<1.0.0") is True
    assert satisfies_constraint("1.0.0", ">=0.1.0,<1.0.0") is False


def test_checker_accepts_compatible_pack():
    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs={},
    )
    pack = _manifest(requires_platform_version=">=0.1.0")

    result = checker.check(pack)

    assert result.is_compatible
    assert result.issues == ()


def test_checker_rejects_pack_with_unmet_platform_constraint():
    checker = PackCompatibilityChecker(
        platform_version="0.1.0",
        installed_packs={},
    )
    pack = _manifest(requires_platform_version=">=0.2.0")

    result = checker.check(pack)

    assert not result.is_compatible
    assert any("platform" in issue for issue in result.issues)


def test_checker_flags_missing_dependency():
    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs={},
    )
    pack = _manifest(dependencies=("ha_core",))

    result = checker.check(pack)

    assert not result.is_compatible
    assert result.issues == ("missing dependency: ha_core",)


def test_checker_accepts_dependency_present_at_any_version_when_no_constraint():
    installed = {"ha_core": _manifest(pack_key="ha_core", version="9.9.9")}
    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs=installed,
    )
    pack = _manifest(dependencies=("ha_core",))

    result = checker.check(pack)

    assert result.is_compatible


def test_checker_rejects_dependency_with_unmet_version_constraint():
    installed = {"ha_core": _manifest(pack_key="ha_core", version="0.5.0")}
    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs=installed,
    )
    pack = _manifest(dependencies=("ha_core>=1.0.0",))

    result = checker.check(pack)

    assert not result.is_compatible
    assert any("does not satisfy" in issue for issue in result.issues)


def test_checker_warns_on_unknown_publication_key():
    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs={},
        known_publication_keys=frozenset({"rpt_current_dim_entity"}),
    )
    pack = _manifest(publication_relations=("rpt_ghost_publication",))

    result = checker.check(pack)

    assert result.is_compatible
    assert result.warnings == ("unknown publication key: rpt_ghost_publication",)


def test_checker_does_not_warn_when_known_publications_empty():
    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs={},
    )
    pack = _manifest(publication_relations=("rpt_anything",))

    result = checker.check(pack)

    assert result.is_compatible
    assert result.warnings == ()


def test_checker_accepts_adapter_pack_via_specialization():
    from packages.adapters.contracts import AdapterPack

    checker = PackCompatibilityChecker(
        platform_version="0.2.0",
        installed_packs={"ha_core": _manifest(pack_key="ha_core", version="1.0")},
    )
    pack = AdapterPack(
        pack_key="unit_pack",
        display_name="Unit Pack",
        version="1.0",
        trust_level=TrustLevel.LOCAL,
        dependencies=("ha_core>=1.0",),
    )

    result = checker.check(pack)

    assert result.is_compatible


def test_checker_aggregates_multiple_issues():
    checker = PackCompatibilityChecker(
        platform_version="0.1.0",
        installed_packs={},
    )
    pack = _manifest(
        requires_platform_version=">=0.2.0",
        dependencies=("ha_core",),
    )

    result = checker.check(pack)

    assert not result.is_compatible
    assert len(result.issues) == 2
