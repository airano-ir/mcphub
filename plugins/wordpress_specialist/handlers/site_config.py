"""F.19.6.A — Site config surface (identity + reading + permalinks).

First consumer of the ``settings`` tier introduced by F.19.2.0.
Six tools split across three small surfaces — every one of them is
reachable from the WP-Admin Settings menu, no companion magic, just
a typed REST face for what an editor would otherwise click through.

Surface map (all on the ``settings`` tier):

* **Site identity** (2 tools, ``/admin/site/identity``):
  ``wp_site_identity_get`` reads title / tagline / site_icon /
  custom_logo / blog_charset / WP version. ``wp_site_identity_set``
  writes title / tagline / site_icon_id / custom_logo_id.
* **Reading** (2 tools, ``/admin/site/reading``):
  ``wp_reading_settings_get`` / ``wp_reading_settings_set`` cover
  show_on_front (posts vs page), page_on_front, page_for_posts,
  posts_per_page, blog_public (search-engine visibility). The
  ``blog_public=false`` write surfaces a hint reminding the caller
  the change asks search engines not to index but is non-binding.
* **Permalinks** (2 tools, ``/admin/permalinks``):
  ``wp_permalinks_get`` / ``wp_permalinks_set``. After a write the
  companion calls ``flush_rewrite_rules()`` so the new structure
  takes effect immediately — same as the manual save on
  Settings → Permalinks.

Security rules: route-level ``manage_options`` only. No new S-rules
this round — every operation maps to a stock WP option write that
WP-Admin would do in a single click. WP's own ``sanitize_option_*``
hooks fire on each ``update_option`` and provide the safe-input gate.

All tools require Airano MCP Bridge v2.16.0+.
"""

from __future__ import annotations

import re
from typing import Any

from plugins.wordpress.client import WordPressClient

# Companion admin namespace — same prefix used by F.19.1 / F.19.5 /
# F.19.7 / F.19.2.1.
_ADMIN_NS = "airano-mcp/v1/admin"

# Permalink structure tokens WP recognises. Anything else is rejected
# client-side as a cheap pre-check (the companion is the binding gate
# — it round-trips through WP's own ``permalink_structure`` sanitiser).
_PERMALINK_TOKEN_RE = re.compile(r"^(/|%[a-z_]+%|[A-Za-z0-9_\-])+$")
_PERMALINK_MAX_LEN = 256

# Reading-settings ``show_on_front`` accepts only these two strings —
# matches WP's own constant enum.
_SHOW_ON_FRONT_VALUES = {"posts", "page"}


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for the F.19.6.A site config surface."""
    return [
        # ───── Site identity (2) ─────────────────────────────────────
        {
            "name": "wp_site_identity_get",
            "method_name": "wp_site_identity_get",
            "description": (
                "Read site identity: title (blogname), tagline "
                "(blogdescription), site_icon (favicon attachment id), "
                "custom_logo (theme logo attachment id), blog_charset, "
                "WP version, and admin email. Companion-backed read so "
                "responses stay consistent with the writer route. "
                "Requires Airano MCP Bridge v2.16.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_site_identity_set",
            "method_name": "wp_site_identity_set",
            "description": (
                "Update site identity. Pass any subset of title / "
                "tagline / site_icon_id / custom_logo_id (omitted keys "
                "are left untouched). Attachment ids are validated by "
                "the companion against WP's media library — invalid "
                "ids return ``invalid_attachment``. Requires Airano "
                "MCP Bridge v2.16.0+ and manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Site title (option ``blogname``).",
                        "maxLength": 255,
                    },
                    "tagline": {
                        "type": "string",
                        "description": "Site tagline (option ``blogdescription``).",
                        "maxLength": 1024,
                    },
                    "site_icon_id": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "Attachment id for the site icon (favicon). "
                            "Pass 0 to clear; pass an integer >= 1 to set."
                        ),
                    },
                    "custom_logo_id": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "Attachment id for the theme custom logo. "
                            "Pass 0 to clear; the active theme must "
                            "declare ``custom-logo`` support."
                        ),
                    },
                },
            },
            "scope": "settings",
        },
        # ───── Reading settings (2) ──────────────────────────────────
        {
            "name": "wp_reading_settings_get",
            "method_name": "wp_reading_settings_get",
            "description": (
                "Read the Settings → Reading panel: show_on_front "
                "(``posts`` or ``page``), page_on_front, "
                "page_for_posts, posts_per_page, posts_per_rss, and "
                "blog_public (search-engine visibility flag — 0 means "
                "WP asks crawlers not to index). Requires Airano MCP "
                "Bridge v2.16.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_reading_settings_set",
            "method_name": "wp_reading_settings_set",
            "description": (
                "Update Settings → Reading values. Pass any subset of "
                "show_on_front / page_on_front / page_for_posts / "
                "posts_per_page / posts_per_rss / blog_public. When "
                "show_on_front=='page', page_on_front must be set to a "
                "published Page id (companion validates). Setting "
                "blog_public=false tells crawlers not to index — the "
                "directive is non-binding, real privacy still belongs "
                "to httpd auth or membership plugins. Requires Airano "
                "MCP Bridge v2.16.0+ and manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "show_on_front": {
                        "type": "string",
                        "enum": ["posts", "page"],
                        "description": (
                            "``posts`` shows the latest blog posts on "
                            "the home URL; ``page`` uses two static "
                            "pages (front + posts archive)."
                        ),
                    },
                    "page_on_front": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "Page id used as the static front page "
                            "(only consulted when show_on_front=page)."
                        ),
                    },
                    "page_for_posts": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "Page id used as the blog posts archive "
                            "(only consulted when show_on_front=page)."
                        ),
                    },
                    "posts_per_page": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Posts shown per page on archives + the home feed.",
                    },
                    "posts_per_rss": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Items emitted in RSS / Atom feeds.",
                    },
                    "blog_public": {
                        "type": "boolean",
                        "description": (
                            "true = invite search engines to index; "
                            "false = ask crawlers not to. Non-binding."
                        ),
                    },
                },
            },
            "scope": "settings",
        },
        # ───── Permalinks (2) ────────────────────────────────────────
        {
            "name": "wp_permalinks_get",
            "method_name": "wp_permalinks_get",
            "description": (
                "Read the current permalink structure (option "
                "``permalink_structure``) plus the category_base + "
                "tag_base prefixes. Empty string in ``structure`` "
                'means "plain" permalinks (?p=N). Requires Airano '
                "MCP Bridge v2.16.0+ and manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_permalinks_set",
            "method_name": "wp_permalinks_set",
            "description": (
                "Update the permalink structure. Common safe values: "
                "``/%postname%/``, ``/%year%/%monthnum%/%postname%/``, "
                "``/%category%/%postname%/``. Pass an empty string for "
                "plain permalinks. The companion writes the option "
                "then calls ``flush_rewrite_rules()`` so the new "
                "structure takes effect immediately. Optional "
                "category_base / tag_base override the default "
                "``category`` / ``tag`` prefixes. Requires Airano MCP "
                "Bridge v2.16.0+ and manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "structure": {
                        "type": "string",
                        "description": (
                            "Permalink template using WP tokens "
                            "(``%postname%``, ``%post_id%``, ``%year%``, "
                            "``%monthnum%``, ``%day%``, ``%hour%``, "
                            "``%minute%``, ``%second%``, ``%category%``, "
                            "``%author%``). Empty string = plain."
                        ),
                        "maxLength": _PERMALINK_MAX_LEN,
                    },
                    "category_base": {
                        "type": "string",
                        "description": "Category archive prefix (default ``category``).",
                        "maxLength": 64,
                    },
                    "tag_base": {
                        "type": "string",
                        "description": "Tag archive prefix (default ``tag``).",
                        "maxLength": 64,
                    },
                },
                "required": ["structure"],
            },
            "scope": "settings",
        },
    ]


# ─────────────────────────────────────────────────────────────────────
# Client-side validation helpers
# ─────────────────────────────────────────────────────────────────────


def _validate_permalink_structure(structure: Any) -> str:
    """Cheap structural pre-check for permalink_structure.

    Empty string ("plain" permalinks) is valid. Otherwise we accept
    only `/`, `%token%`, alphanumerics, `_`, and `-`. The companion's
    ``sanitize_option_permalink_structure`` is the binding sanitiser.
    """
    if not isinstance(structure, str):
        raise ValueError("structure must be a string")
    if structure == "":
        return ""
    if len(structure) > _PERMALINK_MAX_LEN:
        raise ValueError(f"structure exceeds {_PERMALINK_MAX_LEN} char cap")
    if "\x00" in structure:
        raise ValueError("structure must not contain null bytes")
    if not _PERMALINK_TOKEN_RE.match(structure):
        raise ValueError(
            "structure may only contain `/`, `%token%`, alnum, `_`, `-` "
            "(got unexpected character)"
        )
    return structure


def _validate_attachment_id(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer (got {value!r})")
    return value


class SiteConfigHandler:
    """Site identity + reading + permalinks surface (F.19.6.A).

    Each method returns the parsed JSON envelope from the companion.
    The plugin.py wrapper is responsible for serialising for MCP
    transport.
    """

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    # ── Identity ────────────────────────────────────────────────────

    async def wp_site_identity_get(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/site/identity",
            use_custom_namespace=True,
        )

    async def wp_site_identity_set(
        self,
        title: str | None = None,
        tagline: str | None = None,
        site_icon_id: int | None = None,
        custom_logo_id: int | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if title is not None:
            if not isinstance(title, str):
                raise ValueError("title must be a string")
            body["title"] = title
        if tagline is not None:
            if not isinstance(tagline, str):
                raise ValueError("tagline must be a string")
            body["tagline"] = tagline
        if site_icon_id is not None:
            body["site_icon_id"] = _validate_attachment_id(site_icon_id, "site_icon_id")
        if custom_logo_id is not None:
            body["custom_logo_id"] = _validate_attachment_id(custom_logo_id, "custom_logo_id")
        if not body:
            raise ValueError("wp_site_identity_set requires at least one field to update")
        return await self.client.post(
            f"{_ADMIN_NS}/site/identity",
            json_data=body,
            use_custom_namespace=True,
        )

    # ── Reading ─────────────────────────────────────────────────────

    async def wp_reading_settings_get(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/site/reading",
            use_custom_namespace=True,
        )

    async def wp_reading_settings_set(
        self,
        show_on_front: str | None = None,
        page_on_front: int | None = None,
        page_for_posts: int | None = None,
        posts_per_page: int | None = None,
        posts_per_rss: int | None = None,
        blog_public: bool | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if show_on_front is not None:
            if show_on_front not in _SHOW_ON_FRONT_VALUES:
                raise ValueError(
                    f"show_on_front must be one of {sorted(_SHOW_ON_FRONT_VALUES)} "
                    f"(got {show_on_front!r})"
                )
            body["show_on_front"] = show_on_front
        if page_on_front is not None:
            body["page_on_front"] = _validate_attachment_id(page_on_front, "page_on_front")
        if page_for_posts is not None:
            body["page_for_posts"] = _validate_attachment_id(page_for_posts, "page_for_posts")
        if posts_per_page is not None:
            if not isinstance(posts_per_page, int) or isinstance(posts_per_page, bool):
                raise ValueError("posts_per_page must be an integer")
            if posts_per_page < 1 or posts_per_page > 100:
                raise ValueError("posts_per_page must be between 1 and 100")
            body["posts_per_page"] = posts_per_page
        if posts_per_rss is not None:
            if not isinstance(posts_per_rss, int) or isinstance(posts_per_rss, bool):
                raise ValueError("posts_per_rss must be an integer")
            if posts_per_rss < 1 or posts_per_rss > 100:
                raise ValueError("posts_per_rss must be between 1 and 100")
            body["posts_per_rss"] = posts_per_rss
        if blog_public is not None:
            if not isinstance(blog_public, bool):
                raise ValueError("blog_public must be a boolean")
            body["blog_public"] = blog_public
        if not body:
            raise ValueError("wp_reading_settings_set requires at least one field to update")
        return await self.client.post(
            f"{_ADMIN_NS}/site/reading",
            json_data=body,
            use_custom_namespace=True,
        )

    # ── Permalinks ──────────────────────────────────────────────────

    async def wp_permalinks_get(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/permalinks",
            use_custom_namespace=True,
        )

    async def wp_permalinks_set(
        self,
        structure: str,
        category_base: str | None = None,
        tag_base: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"structure": _validate_permalink_structure(structure)}
        if category_base is not None:
            if not isinstance(category_base, str) or len(category_base) > 64:
                raise ValueError("category_base must be a string up to 64 chars")
            body["category_base"] = category_base
        if tag_base is not None:
            if not isinstance(tag_base, str) or len(tag_base) > 64:
                raise ValueError("tag_base must be a string up to 64 chars")
            body["tag_base"] = tag_base
        return await self.client.post(
            f"{_ADMIN_NS}/permalinks",
            json_data=body,
            use_custom_namespace=True,
        )
