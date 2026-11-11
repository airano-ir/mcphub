"""Google Search Console Plugin — Clean Architecture.

Read-only access to Google Search Console via the Search Console REST API v1
using an OAuth refresh token (scope ``webmasters.readonly``). Provides
property discovery, sitemap listing, URL Inspection, and Search Analytics
queries with bounded dimensions/date ranges.

The plugin receives per-site credentials (refresh_token, optionally
access_token and token_expires_at) decrypted from the SQLite store at call
time. Token refresh uses GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET from
environment variables. All tools are read-only — no write endpoints are
called.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.google_search_console import handlers
from plugins.google_search_console.client import GSCClient


class GoogleSearchConsolePlugin(BasePlugin):
    """Google Search Console plugin — Clean architecture.

    Provides read-only Search Console capabilities:
    - Property listing (with permission levels)
    - Sitemap listing and status
    - URL Inspection (index status, mobile usability, rich results)
    - Search Analytics queries (clicks, impressions, CTR, position)
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier."""
        return "google_search_console"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys.

        The OAuth flow stores ``refresh_token`` in the encrypted credentials.
        ``access_token`` and ``token_expires_at`` are optional (the client
        refreshes them on demand using the refresh token).
        """
        return ["refresh_token"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """Initialize the GSC plugin.

        Args:
            config: Configuration dictionary containing:
                - refresh_token: Long-lived Google refresh token (webmasters.readonly)
                - access_token: (Optional) Short-lived access token
                - token_expires_at: (Optional) ISO timestamp of token expiry
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        self.client = GSCClient(
            refresh_token=config["refresh_token"],
            access_token=config.get("access_token"),
            token_expires_at=config.get("token_expires_at"),
        )

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """Return all tool specifications for ToolGenerator."""
        specs: list[dict[str, Any]] = []
        specs.extend(handlers.properties.get_tool_specifications())
        specs.extend(handlers.sitemaps.get_tool_specifications())
        specs.extend(handlers.url_inspection.get_tool_specifications())
        specs.extend(handlers.analytics.get_tool_specifications())
        return specs

    def __getattr__(self, name: str):
        """Dynamically delegate method calls to handler modules.

        Args:
            name: Method name being called.

        Returns:
            Handler function from the properties, sitemaps, url_inspection,
            or analytics handler module.
        """
        handler_modules = [
            handlers.properties,
            handlers.sitemaps,
            handlers.url_inspection,
            handlers.analytics,
        ]

        for module in handler_modules:
            if hasattr(module, name):
                func = getattr(module, name)

                async def wrapper(_func=func, **kwargs):
                    return await _func(self.client, **kwargs)

                return wrapper

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def health_check(self) -> dict[str, Any]:
        """Check if the Search Console API is accessible via the refresh token."""
        try:
            sites = await self.client.list_sites()
            count = len(sites.get("siteEntry", []))
            return {
                "healthy": True,
                "message": f"Search Console accessible — {count} properties found",
            }
        except Exception as e:
            return {"healthy": False, "message": f"GSC health check failed: {str(e)}"}

    async def probe_credential_capabilities(self) -> dict[str, Any]:
        """Report what the GSC credential can do.

        The refresh token's scope (``webmasters.readonly``) is fixed at consent
        time and not discoverable from the API itself, so report the known
        granted capability set deterministically after confirming the token
        refreshes successfully via ``sites.list``.
        """
        try:
            await self.client.list_sites()
        except Exception as exc:  # noqa: BLE001
            return {
                "probe_available": False,
                "granted": [],
                "source": "gsc_oauth_scope",
                "reason": f"sites_list_failed: {exc}",
            }

        return {
            "probe_available": True,
            "granted": [
                "gsc.read",  # list properties, sitemaps, URL inspection, search analytics
            ],
            "source": "gsc_oauth_scope",
            "reason": "sites_list_ok",
        }
