"""Contract assertions run through the PackCompatibilityChecker.

Every in-repo pack must pass the compatibility check against the
current platform (with all in-repo packs installed). The synthetic
external pack must pass when its declared platform constraint is met
and must fail cleanly when it isn't.
"""

from __future__ import annotations

from packages.adapters.pack_compatibility import PackCompatibilityChecker

PLATFORM_VERSION = "0.2.0"


def test_every_in_repo_pack_is_compatible_with_current_platform(in_repo_packs):
    installed = {pack.pack_key: pack.to_pack_manifest() for pack in in_repo_packs}
    checker = PackCompatibilityChecker(
        platform_version=PLATFORM_VERSION,
        installed_packs=installed,
    )
    for pack in in_repo_packs:
        result = checker.check(pack)
        assert result.is_compatible, (
            f"{pack.pack_key}: compatibility check failed with issues={result.issues!r}"
        )


def test_synthetic_external_pack_is_compatible_when_platform_constraint_met(
    synthetic_external_pack,
):
    checker = PackCompatibilityChecker(
        platform_version=PLATFORM_VERSION,
        installed_packs={},
    )
    result = checker.check(synthetic_external_pack)
    assert result.is_compatible
    assert result.issues == ()


def test_synthetic_external_pack_fails_cleanly_on_older_platform(
    synthetic_external_pack,
):
    checker = PackCompatibilityChecker(
        platform_version="0.0.9",
        installed_packs={},
    )
    result = checker.check(synthetic_external_pack)
    assert not result.is_compatible
    assert any("platform" in issue for issue in result.issues)
