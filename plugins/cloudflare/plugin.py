"""Cloudflare Plugin — Clean Architecture.

Static-credential plugin for Cloudflare API v4 (per-site ``api_token``).
Provides read, write, and admin-classified tools across:

- User / token verification and account discovery
- Zones (list, details, cache purge)
- DNS records (list, get, create, update, delete)
- Workers scripts (list, get, delete)
- KV namespaces and keys (list, get, create, put, delete)
- R2 buckets (list, get, create, delete)

Scope classification follows the hub's universal scope tiers: destructive
tools (deletes) are ``admin``, non-destructive mutations are ``write``,
inventory/diagnostics are ``read``.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.cloudflare import handlers
from plugins.cloudflare.client import CloudflareClient


class CloudflarePlugin(BasePlugin):
    """Cloudflare project plugin — Clean architecture.

    Publicly visible plugin (in DEFAULT_PUBLIC_PLUGINS): every user can
    connect their own Cloudflare account with a scoped API token.
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier."""
        return "cloudflare"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys.

        ``api_token`` is mandatory. ``account_id`` is optional — when
        omitted, the client discovers the first account the token can see.
        """
        return ["api_token"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """Initialize the Cloudflare plugin.

        Args:
            config: Configuration dictionary containing:
                - api_token: Cloudflare API Token (Bearer auth).
                - account_id: (Optional) Account id for Workers/KV/R2.
            project_id: Optional project ID (auto-generated if not provided).
        """
        super().__init__(config, project_id=project_id)

        self.client = CloudflareClient(
            api_token=config["api_token"],
            account_id=config.get("account_id"),
        )

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """Return all tool specifications for ToolGenerator.

        Returns:
            List of tool specification dictionaries (25 tools).
        """
        specs: list[dict[str, Any]] = []
        specs.extend(handlers.user.get_tool_specifications())
        specs.extend(handlers.zones.get_tool_specifications())
        specs.extend(handlers.dns.get_tool_specifications())
        specs.extend(handlers.workers.get_tool_specifications())
        specs.extend(handlers.kv.get_tool_specifications())
        specs.extend(handlers.r2.get_tool_specifications())
        return specs

    def __getattr__(self, name: str):
        """Dynamically delegate method calls to handler modules.

        Args:
            name: Method name being called.

        Returns:
            Handler function from the matching handler module.
        """
        handler_modules = [
            handlers.user,
            handlers.zones,
            handlers.dns,
            handlers.workers,
            handlers.kv,
            handlers.r2,
        ]

        for module in handler_modules:
            if hasattr(module, name):
                func = getattr(module, name)

                async def wrapper(_func=func, **kwargs):
                    return await _func(self.client, **kwargs)

                return wrapper

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def health_check(self) -> dict[str, Any]:
        """Check if the Cloudflare API is accessible with the stored token.

        Uses ``/user/tokens/verify`` — works with any token regardless of
        permissions.

        Returns:
            Dict containing health check result.
        """
        try:
            result = await self.client.verify_token()
            status = result.get("status", "unknown")
            token_id = result.get("id", "?")
            return {
                "healthy": status == "active",
                "message": (
                    f"Cloudflare token {status} (id {token_id})"
                    if status == "active"
                    else f"Cloudflare token status: {status}"
                ),
            }
        except Exception as e:
            return {"healthy": False, "message": f"Cloudflare health check failed: {str(e)}"}

    async def probe_credential_capabilities(self) -> dict[str, Any]:
        """Report what the Cloudflare token can do.

        Cloudflare API tokens do not expose their permission set via the
        API — ``/user/tokens/verify`` only returns id + status. Report the
        verified token deterministically instead of guessing permissions.

        Returns:
            Dict with ``probe_available``, ``granted``, ``source`` and
            the verified token id.
        """
        try:
            result = await self.client.verify_token()
            status = result.get("status", "")
            token_id = result.get("id", "")
            if status != "active":
                return {
                    "probe_available": False,
                    "granted": [],
                    "source": "cloudflare_token_verify",
                    "reason": f"token_status_{status}",
                }
            return {
                "probe_available": True,
                "granted": ["token_active"],
                "source": "cloudflare_token_verify",
                "token_id": token_id,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "probe_available": False,
                "granted": [],
                "source": "cloudflare_token_verify",
                "reason": f"probe_failed: {exc}",
            }
