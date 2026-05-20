"""F.19.1 — WordPress Specialist read-only management handler.

Surfaces the ``airano-mcp/v1/admin/*`` companion routes (plugins, themes,
users, options, cron, maintenance) as MCP tools. Read-only in this
iteration; write operations land in F.19.2 once user-supplied security
rules are folded in.

All tools require companion plugin v2.11.0+ and the saved Application
Password to belong to a WordPress user with ``manage_options``. Behaviour
when the companion is missing or auth is insufficient is delegated to
the companion's own error responses, which arrive as ``rest_no_route``
or ``rest_forbidden`` from WordPress core.
"""

from typing import Any

from plugins.wordpress.client import WordPressClient

# Single-source admin namespace prefix. The companion plugin registers
# routes under this prefix in airano-mcp-bridge.php register_rest_routes().
_ADMIN_NS = "airano-mcp/v1/admin"


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for the F.19.1 read-only admin surface."""
    return [
        {
            "name": "wp_plugin_list",
            "method_name": "wp_plugin_list",
            "description": (
                "List every plugin known to WordPress with active/network-active "
                "status, version, author, and update availability. Read-only "
                "(no install/activate). Requires Airano MCP Bridge v2.11.0+ "
                "and a WordPress user with manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_theme_list",
            "method_name": "wp_theme_list",
            "description": (
                "List every installed theme: stylesheet/template names, "
                "version, parent, block-theme flag, active flag, update "
                "availability. Requires Airano MCP Bridge v2.11.0+ and "
                "manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_user_list",
            "method_name": "wp_user_list",
            "description": (
                "List WordPress users with id, username, email, display name, "
                "roles, and registration timestamp. Supports optional role "
                "and search filters; paginated up to 200 per call. Requires "
                "Airano MCP Bridge v2.11.0+ and manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "description": "Filter by role slug (e.g. 'administrator', 'editor').",
                    },
                    "search": {
                        "type": "string",
                        "description": "Search across login, email, and display name.",
                    },
                    "page": {"type": "integer", "minimum": 1, "default": 1},
                    "per_page": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 50,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "wp_option_get",
            "method_name": "wp_option_get",
            "description": (
                "Read a single WordPress option by name. Refuses keys that "
                "look like credentials (suffix matches secret/password/"
                "api_key/token/auth_key/auth_salt etc.) — operators can "
                "still inspect those via wp-admin if needed. Requires "
                "Airano MCP Bridge v2.11.0+ and manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Option key (alphanumerics, dashes, underscores).",
                    }
                },
                "required": ["name"],
            },
            "scope": "read",
        },
        {
            "name": "wp_cron_list",
            "method_name": "wp_cron_list",
            "description": (
                "Dump the WordPress cron table: hook name, next run time "
                "(epoch + ISO 8601 UTC), schedule slug, interval, and "
                "stored args. Requires Airano MCP Bridge v2.11.0+ and "
                "manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_maintenance_status",
            "method_name": "wp_maintenance_status",
            "description": (
                "Report whether WordPress is currently in maintenance mode "
                "by inspecting the .maintenance sentinel file. Returns "
                "``enabled``, ``started_at`` (epoch), and ``stale`` (true "
                "when older than 10 minutes — WP's own threshold). "
                "Requires Airano MCP Bridge v2.11.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        # F.19.3.1 — system info ports (companion v2.12.0+). Originally
        # ported from the legacy wordpress_advanced WP-CLI surface
        # (sunset 2026-05-04); kept here as the companion-backed
        # equivalents.
        {
            "name": "wp_system_info",
            "method_name": "wp_system_info",
            "description": (
                "PHP / MySQL / WordPress versions, server software, "
                "memory limits, multisite flag, debug state, and "
                "canonical paths (ABSPATH, plugins, uploads). Companion-"
                "backed; no Docker socket required. Requires Airano MCP "
                "Bridge v2.12.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_php_info",
            "method_name": "wp_php_info",
            "description": (
                "Curated PHP configuration snapshot — sorted extension "
                "list, common ini settings (memory/upload/session/error), "
                "disabled functions, opcache state. Returns structured "
                "JSON, not the full ``phpinfo()`` HTML dump (which would "
                "leak server internals). Requires Airano MCP Bridge "
                "v2.12.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_disk_usage",
            "method_name": "wp_disk_usage",
            "description": (
                "Bytes used by uploads, plugins, and themes plus "
                "filesystem-wide ``disk_total/free/used`` for ABSPATH. "
                "Each tree walk caps at 200k files / 5s wall clock; "
                "truncated walks set ``truncated: true`` so the caller "
                "can treat the value as a lower bound. Requires Airano "
                "MCP Bridge v2.12.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
    ]


class ManagementHandler:
    """Thin wrapper around the companion's ``admin`` namespace.

    Every method awaits a companion REST GET and returns the parsed JSON
    body unchanged so the SPA / MCP client sees the same shape WordPress
    produced. Errors propagate as exceptions raised by ``WordPressClient``;
    the plugin.py wrapper layer is responsible for serialisation.
    """

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    async def wp_plugin_list(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(f"{_ADMIN_NS}/plugins", use_custom_namespace=True)

    async def wp_theme_list(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(f"{_ADMIN_NS}/themes", use_custom_namespace=True)

    async def wp_user_list(
        self,
        role: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 50,
        **_: Any,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": int(page), "per_page": int(per_page)}
        if role:
            params["role"] = role
        if search:
            params["search"] = search
        return await self.client.get(f"{_ADMIN_NS}/users", params=params, use_custom_namespace=True)

    async def wp_option_get(self, name: str, **_: Any) -> dict[str, Any]:
        if not name or not isinstance(name, str):
            raise ValueError("wp_option_get requires a non-empty 'name' string")
        # WordPress option keys are typically [a-zA-Z0-9_-]; the companion
        # route also enforces this via sanitize_key, but reject obvious
        # injection attempts (path traversal, slashes) on the client side
        # so they never reach the wire.
        if "/" in name or ".." in name or "\x00" in name:
            raise ValueError(f"wp_option_get rejected suspicious option name: {name!r}")
        return await self.client.get(f"{_ADMIN_NS}/options/{name}", use_custom_namespace=True)

    async def wp_cron_list(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(f"{_ADMIN_NS}/cron", use_custom_namespace=True)

    async def wp_maintenance_status(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(f"{_ADMIN_NS}/maintenance", use_custom_namespace=True)

    # F.19.3.1 — system info ports (companion v2.12.0+)

    async def wp_system_info(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(f"{_ADMIN_NS}/system-info", use_custom_namespace=True)

    async def wp_php_info(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(f"{_ADMIN_NS}/phpinfo", use_custom_namespace=True)

    async def wp_disk_usage(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(f"{_ADMIN_NS}/disk-usage", use_custom_namespace=True)
