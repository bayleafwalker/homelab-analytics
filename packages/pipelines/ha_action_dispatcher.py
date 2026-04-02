"""Backward-compatible import shim for Home Assistant action dispatcher."""

from packages.domains.homelab.pipelines import ha_action_dispatcher as _impl

__all__ = [name for name in dir(_impl) if not name.startswith("__")]
globals().update({name: getattr(_impl, name) for name in __all__})
