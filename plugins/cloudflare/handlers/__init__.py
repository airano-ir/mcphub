"""Cloudflare plugin handlers — one module per API domain."""

from plugins.cloudflare.handlers import dns, kv, r2, user, workers, zones

__all__ = ["user", "zones", "dns", "workers", "kv", "r2"]
