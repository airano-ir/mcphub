"""F.19.2.1 — Plugin write management (install + activate + delete).

Six tools split across two tiers — the first tools on `wordpress_specialist`
that exercise the `install` and `admin` tiers introduced by F.19.2.0:

* **install tier** (3 tools) — wp.org slug install, activate / deactivate,
  update. These hit `Plugin_Upgrader` / `activate_plugin` /
  `deactivate_plugins` against an already-vetted package source (wp.org
  curated).
* **admin tier** (3 tools) — URL/zip install, plugin delete. These see
  more attack surface (arbitrary zip contents) or have no undo (delete
  drops plugin data).

Surface map:

* `wp_plugin_install_from_slug(slug, activate?)` — install tier
* `wp_plugin_install_from_zip(zip_url | zip_base64, activate?, overwrite?)` — admin tier
* `wp_plugin_activate(slug, network_wide?)` — install tier
* `wp_plugin_deactivate(slug, network_wide?)` — install tier
* `wp_plugin_update(slug)` — install tier
* `wp_plugin_delete(slug)` — admin tier

Security rules layered on top of F.19.2 S-1…S-11 + F.19.5 S-12…S-14
+ F.19.7 S-15…S-19 (companion enforces these regardless of MCPHub-side
guards):

* **S-15 (reused)** — `slug` must match a key in `get_plugins()` on the
  WP side for activate / deactivate / update / delete. install routes
  validate the slug shape on the wire and let `Plugin_Upgrader` handle
  fetch / extraction / verification.
* **S-18 (reused)** — 50 MB cap on install zip payloads.
* **S-20** *(new)* — refuses to delete the Airano MCP Bridge companion
  itself (`airano-mcp-bridge`). Removing the companion via its own
  route would brick the MCP connection; operators must use the WP-Admin
  Plugins page instead.
* **S-21** *(new)* — refuses to deactivate / delete an active plugin
  marked as ``Required: yes`` in its header (rare; some hosts ship
  must-use plugins this way).

All tools require Airano MCP Bridge v2.15.0+.
"""

from __future__ import annotations

import re
from typing import Any

from plugins.wordpress.client import WordPressClient

# Companion admin namespace — same prefix used by F.19.1 / F.19.5 / F.19.7.
_ADMIN_NS = "airano-mcp/v1/admin"

# Mirror of the companion's PLUGIN_ZIP_MAX_BYTES (S-18). The companion
# enforces the binding limit; this is a cheap pre-check to avoid uploading
# a 200 MB payload that will be rejected at the wire anyway.
_PLUGIN_ZIP_MAX_BYTES = 50 * 1024 * 1024  # 50 MB

# Plugin slugs from wp.org are conventionally lowercase letters / digits /
# dashes. Some legacy plugins use underscores; the regex permits both.
# Length cap mirrors WP's own slug sanitiser (sanitize_key + 64 chars).
_PLUGIN_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for the F.19.2.1 plugin write surface."""
    return [
        # ───── Install tier (3) ──────────────────────────────────────
        {
            "name": "wp_plugin_install_from_slug",
            "method_name": "wp_plugin_install_from_slug",
            "description": (
                "Install a plugin from a wp.org slug (e.g. 'akismet'). "
                "Companion calls plugins_api() to resolve the package URL, "
                "downloads via download_url() (so the WP filesystem "
                "abstraction stays engaged), then runs WP core's "
                "Plugin_Upgrader. Set activate=true to activate "
                "immediately on success — activation requires "
                "activate_plugins; companion rejects with rest_forbidden "
                "if missing. Requires Airano MCP Bridge v2.15.0+ and a "
                "WordPress user with install_plugins."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": (
                            "wp.org plugin slug (the 'foo' in "
                            "https://wordpress.org/plugins/foo/). "
                            "Alphanumerics, dashes, underscores only. "
                            "Accepts the ``folder/file.php`` form returned "
                            "by the capabilities probe — everything after "
                            "the first slash is stripped."
                        ),
                    },
                    "activate": {
                        "type": "boolean",
                        "default": False,
                        "description": ("Activate the plugin immediately after install."),
                    },
                },
                "required": ["slug"],
            },
            "scope": "install",
        },
        {
            "name": "wp_plugin_activate",
            "method_name": "wp_plugin_activate",
            "description": (
                "Activate an installed plugin by slug. Companion resolves "
                "the slug to the plugin file via get_plugins() (S-15) and "
                "calls activate_plugin(). When network_wide=true on a "
                "multisite install the plugin is activated network-wide "
                "(requires manage_network_plugins). Requires Airano MCP "
                "Bridge v2.15.0+ and activate_plugins."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": (
                            "Plugin slug (from wp_plugin_list). Accepts "
                            "either the folder-only form (`woocommerce`) "
                            "or the `folder/file.php` form returned by the "
                            "capabilities probe — both are normalised "
                            "client-side."
                        ),
                    },
                    "network_wide": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Activate network-wide on multisite. Ignored "
                            "on single-site installs."
                        ),
                    },
                },
                "required": ["slug"],
            },
            "scope": "install",
        },
        {
            "name": "wp_plugin_deactivate",
            "method_name": "wp_plugin_deactivate",
            "description": (
                "Deactivate an installed plugin by slug. Refuses to "
                "deactivate the Airano MCP Bridge companion itself — "
                "doing so would brick the MCP connection (S-20). "
                "Requires Airano MCP Bridge v2.15.0+ and activate_plugins."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": (
                            "Plugin slug. Accepts folder-only "
                            "(`woocommerce`) or `folder/file.php` form."
                        ),
                    },
                    "network_wide": {
                        "type": "boolean",
                        "default": False,
                        "description": ("Deactivate network-wide on multisite."),
                    },
                },
                "required": ["slug"],
            },
            "scope": "install",
        },
        {
            "name": "wp_plugin_update",
            "method_name": "wp_plugin_update",
            "description": (
                "Update an installed plugin to the latest wp.org version. "
                "Companion checks the cached update_plugins transient + "
                "runs Plugin_Upgrader::upgrade(). Returns no-op (with "
                "``up_to_date: true``) when no update is available rather "
                "than erroring. Requires Airano MCP Bridge v2.15.0+ and "
                "update_plugins."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": (
                            "Plugin slug. Accepts folder-only "
                            "(`woocommerce`) or `folder/file.php` form."
                        ),
                    },
                },
                "required": ["slug"],
            },
            "scope": "install",
        },
        # ───── Admin tier (3) ────────────────────────────────────────
        {
            "name": "wp_plugin_install_from_zip",
            "method_name": "wp_plugin_install_from_zip",
            "description": (
                "Install a plugin from a remote URL or inline base64 zip. "
                "Sees more attack surface than slug install (arbitrary "
                "zip contents) so this lands on the admin tier. Companion "
                "still runs Plugin_Upgrader so signature checks stay "
                "engaged. Pass exactly one of zip_url (companion fetches "
                "via wp_safe_remote_get) or zip_base64 (decoded "
                "server-side). Capped at 50 MB per zip (S-18). Requires "
                "Airano MCP Bridge v2.15.0+ and install_plugins."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "zip_url": {
                        "type": "string",
                        "description": (
                            "https URL the companion will download. "
                            "Mutually exclusive with zip_base64."
                        ),
                    },
                    "zip_base64": {
                        "type": "string",
                        "description": (
                            "Base64-encoded plugin zip body. Capped at " "~50 MB after decode."
                        ),
                    },
                    "activate": {
                        "type": "boolean",
                        "default": False,
                        "description": "Activate after install.",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Permit overwriting an existing plugin with " "the same slug."
                        ),
                    },
                },
            },
            "scope": "admin",
        },
        {
            "name": "wp_plugin_delete",
            "method_name": "wp_plugin_delete",
            "description": (
                "Delete an installed plugin by slug. Refuses to delete "
                "the Airano MCP Bridge companion itself (S-20) and any "
                "currently-active plugin (caller must deactivate first). "
                "Lands on the admin tier because plugin delete drops "
                "the plugin's database tables / options on uninstall — "
                "no undo. Requires Airano MCP Bridge v2.15.0+ and "
                "delete_plugins."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": (
                            "Plugin slug. Accepts folder-only "
                            "(`woocommerce`) or `folder/file.php` form."
                        ),
                    },
                },
                "required": ["slug"],
            },
            "scope": "admin",
        },
    ]


# ─────────────────────────────────────────────────────────────────────
# Client-side validation helpers
# ─────────────────────────────────────────────────────────────────────


def _validate_plugin_slug(slug: Any) -> str:
    """Reject obviously-malformed plugin slugs before the wire.

    Accepts both the folder-only form (``woocommerce``) and the
    ``folder/file.php`` form returned by the WP capabilities probe —
    everything from the first slash onward is stripped, mirroring the
    companion's own normalisation. The companion still does the binding
    ``get_plugins()`` membership check (S-15) for activate / deactivate /
    update / delete — this is just structural defence-in-depth.
    """
    if not isinstance(slug, str):
        raise ValueError("slug must be a string")
    stripped = slug.strip()
    if not stripped:
        raise ValueError("slug must be a non-empty string")
    folder = stripped.split("/", 1)[0]
    if not _PLUGIN_SLUG_RE.match(folder):
        raise ValueError(
            f"slug must be alphanumerics + dashes + underscores "
            f"(<=64 chars, no leading dash); got {slug!r}"
        )
    return folder


class PluginsHandler:
    """Plugin install / activate / deactivate / update / delete surface
    (F.19.2.1).

    Each method returns the parsed JSON envelope from the companion. The
    plugin.py wrapper layer is responsible for serialising the dict for
    MCP transport.
    """

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    # ── Install tier ────────────────────────────────────────────────

    async def wp_plugin_install_from_slug(
        self,
        slug: str,
        activate: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        slug = _validate_plugin_slug(slug)
        return await self.client.post(
            f"{_ADMIN_NS}/plugins/install",
            json_data={"slug": slug, "activate": bool(activate)},
            use_custom_namespace=True,
        )

    async def wp_plugin_activate(
        self,
        slug: str,
        network_wide: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        slug = _validate_plugin_slug(slug)
        return await self.client.post(
            f"{_ADMIN_NS}/plugins/{slug}/activate",
            json_data={"network_wide": bool(network_wide)},
            use_custom_namespace=True,
        )

    async def wp_plugin_deactivate(
        self,
        slug: str,
        network_wide: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        slug = _validate_plugin_slug(slug)
        return await self.client.post(
            f"{_ADMIN_NS}/plugins/{slug}/deactivate",
            json_data={"network_wide": bool(network_wide)},
            use_custom_namespace=True,
        )

    async def wp_plugin_update(self, slug: str, **_: Any) -> dict[str, Any]:
        slug = _validate_plugin_slug(slug)
        return await self.client.post(
            f"{_ADMIN_NS}/plugins/{slug}/update",
            json_data={},
            use_custom_namespace=True,
        )

    # ── Admin tier ──────────────────────────────────────────────────

    async def wp_plugin_install_from_zip(
        self,
        zip_url: str | None = None,
        zip_base64: str | None = None,
        activate: bool = False,
        overwrite: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        if not zip_url and not zip_base64:
            raise ValueError("wp_plugin_install_from_zip requires zip_url or zip_base64")
        if zip_url and zip_base64:
            raise ValueError("wp_plugin_install_from_zip accepts zip_url OR zip_base64, not both")
        body: dict[str, Any] = {
            "activate": bool(activate),
            "overwrite": bool(overwrite),
        }
        if zip_url:
            if not isinstance(zip_url, str):
                raise ValueError("zip_url must be a string")
            body["zip_url"] = zip_url
        else:
            if not isinstance(zip_base64, str):
                raise ValueError("zip_base64 must be a string")
            decoded_size_upper_bound = len(zip_base64) * 3 // 4
            if decoded_size_upper_bound > _PLUGIN_ZIP_MAX_BYTES:
                raise ValueError(
                    f"zip_base64 decodes to roughly {decoded_size_upper_bound} bytes "
                    f"— exceeds {_PLUGIN_ZIP_MAX_BYTES} byte cap (S-18)"
                )
            body["zip_base64"] = zip_base64
        return await self.client.post(
            f"{_ADMIN_NS}/plugins/install",
            json_data=body,
            use_custom_namespace=True,
        )

    async def wp_plugin_delete(self, slug: str, **_: Any) -> dict[str, Any]:
        slug = _validate_plugin_slug(slug)
        return await self.client.delete(
            f"{_ADMIN_NS}/plugins/{slug}",
            use_custom_namespace=True,
        )
