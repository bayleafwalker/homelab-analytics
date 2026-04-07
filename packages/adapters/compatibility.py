"""Compatibility evaluation for adapter packs.

Provides validation and compatibility checking for AdapterPack structures,
ensuring they meet platform requirements and contain valid manifests.
"""

from __future__ import annotations

from packages.adapters.contracts import AdapterPack, CompatibilityCheck, TrustLevel


def check_compatibility(pack: AdapterPack, *, platform_version: str = "") -> CompatibilityCheck:
    """Evaluate whether a pack is compatible with the current platform.

    Parameters
    ----------
    pack : AdapterPack
        The adapter pack to check for compatibility.
    platform_version : str, optional
        The current platform version (e.g., "1.5.2"). If empty, version
        constraints cannot be verified. Default is "".

    Returns
    -------
    CompatibilityCheck
        Contains is_compatible (True if no issues), issues (blocking reasons),
        and warnings (non-blocking concerns).

    Rules
    -----
    - If pack.requires_platform_version is non-empty and platform_version is empty,
      add warning about unknown version.
    - If both are non-empty, compare major versions (first segment split on ".").
      Add issue if they don't match.
    - If trust_level is LOCAL, add warning.
    - If trust_level is COMMUNITY, add warning.
    - If pack has no adapters AND no renderers, add issue.
    - is_compatible is True only if there are no issues.
    """
    issues = []
    warnings = []

    # Check version constraint
    if pack.requires_platform_version and not platform_version:
        warnings.append(
            f"Platform version unknown; cannot verify version constraint '{pack.requires_platform_version}'"
        )
    elif pack.requires_platform_version and platform_version:
        # Extract major version (first segment before ".")
        pack_major = pack.requires_platform_version.split(".")[0]
        platform_major = platform_version.split(".")[0]
        if pack_major != platform_major:
            issues.append(
                f"Pack requires platform version '{pack.requires_platform_version}', got '{platform_version}'"
            )

    # Check trust level
    if pack.trust_level == TrustLevel.LOCAL:
        warnings.append(f"Pack '{pack.pack_key}' has LOCAL trust level; no external verification")
    elif pack.trust_level == TrustLevel.COMMUNITY:
        warnings.append(f"Pack '{pack.pack_key}' has COMMUNITY trust level; review before activating in production")

    # Check for empty pack
    if not pack.adapters and not pack.renderers:
        issues.append(f"Pack '{pack.pack_key}' contains no adapters or renderers")

    return CompatibilityCheck(
        is_compatible=len(issues) == 0,
        issues=tuple(issues),
        warnings=tuple(warnings),
    )


def validate_adapter_pack(pack: AdapterPack) -> list[str]:
    """Validate the structural integrity of an adapter pack.

    Parameters
    ----------
    pack : AdapterPack
        The adapter pack to validate.

    Returns
    -------
    list[str]
        List of validation error messages. Empty list means the pack is valid.

    Rules
    -----
    - pack_key must be non-empty.
    - display_name must be non-empty.
    - version must be non-empty.
    - Each adapter in pack.adapters must have non-empty adapter_key.
    - Each renderer in pack.renderers must have non-empty renderer_key.
    - No duplicate adapter_key values.
    - No duplicate renderer_key values.
    """
    errors = []

    # Check required fields
    if not pack.pack_key:
        errors.append("pack_key must be non-empty")
    if not pack.display_name:
        errors.append("display_name must be non-empty")
    if not pack.version:
        errors.append("version must be non-empty")

    # Check adapter keys
    adapter_keys = []
    for adapter_manifest in pack.adapters:
        if not adapter_manifest.adapter_key:
            errors.append(f"adapter '{adapter_manifest.adapter_key}' has empty adapter_key")
        else:
            adapter_keys.append(adapter_manifest.adapter_key)

    # Check for duplicate adapter keys
    seen = set()
    for key in adapter_keys:
        if key in seen:
            errors.append(f"duplicate adapter_key: '{key}'")
        seen.add(key)

    # Check renderer keys
    renderer_keys = []
    for renderer_manifest in pack.renderers:
        if not renderer_manifest.renderer_key:
            errors.append(f"renderer '{renderer_manifest.renderer_key}' has empty renderer_key")
        else:
            renderer_keys.append(renderer_manifest.renderer_key)

    # Check for duplicate renderer keys
    seen = set()
    for key in renderer_keys:
        if key in seen:
            errors.append(f"duplicate renderer_key: '{key}'")
        seen.add(key)

    return errors
