"""Adapter ecosystem API routes — contract exposure and registry metadata.

Endpoints:
  GET /adapters/packs              → list all registered packs (manifests, trust level, active state)
  GET /adapters/packs/{pack_key}   → detail for one pack
  GET /adapters/renderers          → list all renderer manifests across active packs
  GET /adapters/contracts          → contract surface summary (directions, capability vocabulary)
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException

from packages.adapters.contracts import AdapterDirection, TrustLevel
from packages.adapters.registry import AdapterRegistry


def register_adapter_routes(
    app: FastAPI,
    *,
    adapter_registry: AdapterRegistry,
    require_unsafe_admin: Callable[[], None],
) -> None:
    """Register adapter ecosystem API routes.

    Parameters
    ----------
    app : FastAPI
        FastAPI application instance.
    adapter_registry : AdapterRegistry
        Registry of registered adapter packs.
    require_unsafe_admin : Callable[[], None]
        Callable that raises HTTPException if unsafe admin is not enabled.
    """

    @app.get("/adapters/packs")
    async def list_adapter_packs() -> dict[str, Any]:
        """List all registered adapter packs with summary metadata.

        Returns
        -------
        dict[str, Any]
            Response with 'packs' key containing list of pack summaries.
        """
        require_unsafe_admin()
        packs = adapter_registry.list_packs(active_only=False)
        pack_list = []
        for pack in packs:
            pack_list.append(
                {
                    "pack_key": pack.pack_key,
                    "display_name": pack.display_name,
                    "version": pack.version,
                    "trust_level": pack.trust_level.value,
                    "active": adapter_registry.is_active(pack.pack_key),
                    "adapter_count": len(pack.adapters),
                    "renderer_count": len(pack.renderers),
                    "description": pack.description,
                }
            )
        return {"packs": pack_list}

    @app.get("/adapters/packs/{pack_key}")
    async def get_adapter_pack(pack_key: str) -> dict[str, Any]:
        """Get detailed information about a specific adapter pack.

        Parameters
        ----------
        pack_key : str
            The pack key to retrieve.

        Returns
        -------
        dict[str, Any]
            Response with pack details including adapters and renderers.

        Raises
        ------
        HTTPException
            404 if the pack is not found.
        """
        require_unsafe_admin()
        pack = adapter_registry.get(pack_key)
        if pack is None:
            raise HTTPException(status_code=404, detail=f"Pack '{pack_key}' not found")

        adapters = [
            {
                "adapter_key": manifest.adapter_key,
                "display_name": manifest.display_name,
                "version": manifest.version,
                "supported_directions": [d.value for d in manifest.supported_directions],
                "supported_entity_classes": list(manifest.supported_entity_classes),
                "credential_requirements": list(manifest.credential_requirements),
                "health_check_contract": manifest.health_check_contract,
                "target_capabilities": list(manifest.target_capabilities),
            }
            for manifest in pack.adapters
        ]

        renderers = [
            {
                "renderer_key": manifest.renderer_key,
                "display_name": manifest.display_name,
                "version": manifest.version,
                "supported_formats": list(manifest.supported_formats),
                "supported_publication_keys": list(manifest.supported_publication_keys),
            }
            for manifest in pack.renderers
        ]

        return {
            "pack_key": pack.pack_key,
            "display_name": pack.display_name,
            "version": pack.version,
            "trust_level": pack.trust_level.value,
            "active": adapter_registry.is_active(pack.pack_key),
            "description": pack.description,
            "requires_platform_version": pack.requires_platform_version,
            "adapters": adapters,
            "renderers": renderers,
        }

    @app.get("/adapters/renderers")
    async def list_renderer_manifests() -> dict[str, Any]:
        """List all renderer manifests from registered packs.

        Returns
        -------
        dict[str, Any]
            Response with 'renderers' key containing list of renderer manifests.
        """
        require_unsafe_admin()
        packs = adapter_registry.list_packs(active_only=False)
        renderers = []
        for pack in packs:
            for manifest in pack.renderers:
                renderers.append(
                    {
                        "renderer_key": manifest.renderer_key,
                        "display_name": manifest.display_name,
                        "version": manifest.version,
                        "supported_formats": list(manifest.supported_formats),
                        "supported_publication_keys": list(manifest.supported_publication_keys),
                    }
                )
        return {"renderers": renderers}

    @app.get("/adapters/contracts")
    async def get_contract_vocabulary() -> dict[str, Any]:
        """Get contract vocabulary summary (directions and trust levels).

        Returns
        -------
        dict[str, Any]
            Response with 'directions' and 'trust_levels' keys.
        """
        require_unsafe_admin()
        return {
            "directions": [d.value for d in AdapterDirection],
            "trust_levels": [t.value for t in TrustLevel],
        }
