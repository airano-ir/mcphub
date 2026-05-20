"""F.19.7 — Theme dev surface (install + file CRUD).

Seven tools split across two surfaces. Both ride the same companion
plugin (Airano MCP Bridge v2.14.0+) and stay on the existing ``editor``
tier introduced by F.19.5 — theme work is the same risk class as page
editing, no new tier needed.

Surface map:

* **Theme management** (3 tools, companion v2.14.0 routes
  ``/admin/themes/*``): ``wp_theme_install_from_zip`` (POST install),
  ``wp_theme_activate``, ``wp_theme_delete``. Install accepts either
  a remote ``zip_url`` (companion downloads via ``wp_safe_remote_get``)
  or an inline ``zip_base64`` (cap 50 MB, decoded server-side). All three
  ride WP core's ``Theme_Upgrader`` so signature checks and the existing
  filesystem abstraction stay engaged.
* **Theme file CRUD** (4 tools, ``/admin/themes/files/*``):
  ``wp_theme_file_list`` (glob walk), ``wp_theme_file_read``,
  ``wp_theme_file_write``, ``wp_theme_file_delete``. Reads/writes go
  through ``WP_Filesystem_Direct`` server-side; payloads round-trip as
  base64 so the JSON envelope stays binary-safe (favicons, fonts, MO
  files, etc.).

Security rules layered on top of F.19.2 S-1…S-11 + F.19.5 S-12…S-14
(companion enforces these regardless of MCPHub-side guards):

* **S-15** — ``theme_slug`` must match a key in ``wp_get_themes()``.
  Companion rejects anything else with ``theme_not_found`` (404).
  MCPHub-side: a structural slug guard (alphanumerics, dashes,
  underscores; no slashes / dots / null bytes / leading dash) so
  malformed slugs don't reach the wire.
* **S-16** — Path canonicalisation. Every file route resolves
  ``wp-content/themes/{slug}/{path}`` via ``realpath()`` and rejects
  results that escape the slug directory. Blocks ``..``, symlinks
  pointing outside, absolute paths, null bytes. MCPHub-side does a
  best-effort structural pre-check (the companion's realpath is the
  binding gate).
* **S-17** — Writing PHP files requires ``current_user_can('edit_themes')``
  AND ``!defined('DISALLOW_FILE_EDIT') || !DISALLOW_FILE_EDIT``. Non-PHP
  files (CSS, JSON, MO/PO, JS, images, fonts) skip the
  ``DISALLOW_FILE_EDIT`` check but still require ``edit_themes``.
* **S-18** — Per-call caps: 5 MB per file, 1000 files per list, 50 MB
  per theme install zip. Companion enforces in PHP; MCPHub rejects
  obviously-oversized payloads before the wire.
* **S-19** — Optimistic concurrency. When ``expected_sha256`` is
  provided on write, the companion compares against the current file
  sha256 and returns ``sha_mismatch`` (409) if it doesn't match. Lets
  agents reason about conflicting edits without locking.

All tools require Airano MCP Bridge v2.14.0+.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from plugins.wordpress.client import WordPressClient

# Companion admin namespace — same prefix used by F.19.1 / F.19.5.
_ADMIN_NS = "airano-mcp/v1/admin"

# Mirrored from the companion's THEME_FILE_MAX_BYTES /
# THEME_LIST_MAX_FILES / THEME_ZIP_MAX_BYTES so MCPHub can reject
# obviously-oversized payloads before they reach the wire (S-18). The
# companion enforces the real limit.
_THEME_FILE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
_THEME_LIST_MAX_FILES = 1000  # files per list call
_THEME_ZIP_MAX_BYTES = 50 * 1024 * 1024  # 50 MB per install zip

# A theme slug from ``wp_get_themes()`` is the directory name under
# ``wp-content/themes`` — WP itself permits letters, digits, hyphens,
# underscores. We add a hard structural guard here as defence-in-depth
# alongside S-15 (the companion's ``wp_get_themes()`` whitelist is the
# binding check).
_THEME_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for the F.19.7 theme dev surface."""
    return [
        # ───── Theme management ──────────────────────────────────────
        {
            "name": "wp_theme_install_from_zip",
            "method_name": "wp_theme_install_from_zip",
            "description": (
                "Install a theme from a remote URL or inline base64 zip. "
                "Companion runs WP core's Theme_Upgrader so signature checks "
                "and the WP filesystem abstraction stay engaged. Pass exactly "
                "one of zip_url (companion fetches via wp_safe_remote_get) or "
                "zip_base64 (decoded server-side). Capped at 50 MB per zip "
                "(S-18). Set activate=true to make the new theme active "
                "after install; overwrite=true permits re-installing a slug "
                "that already exists. Requires Airano MCP Bridge v2.14.0+ "
                "and a WordPress user with install_themes."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "zip_url": {
                        "type": "string",
                        "description": (
                            "https URL the companion will download via "
                            "wp_safe_remote_get. Mutually exclusive with "
                            "zip_base64."
                        ),
                    },
                    "zip_base64": {
                        "type": "string",
                        "description": (
                            "Base64-encoded theme zip body. Capped at "
                            "~50 MB after decode (S-18). Mutually exclusive "
                            "with zip_url."
                        ),
                    },
                    "activate": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Activate the installed theme on success. "
                            "Activation requires switch_themes — companion "
                            "rejects with rest_forbidden if missing."
                        ),
                    },
                    "overwrite": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Permit overwriting an existing theme with the "
                            "same slug. Required if a previous install is "
                            "already on disk."
                        ),
                    },
                },
            },
            "scope": "editor",
        },
        {
            "name": "wp_theme_activate",
            "method_name": "wp_theme_activate",
            "description": (
                "Switch the active theme to ``slug``. Companion verifies the "
                "slug exists in wp_get_themes() (S-15) and the caller holds "
                "switch_themes. Returns the active stylesheet + template "
                "after the switch — useful when activating a child theme "
                "(stylesheet differs from template). Requires Airano MCP "
                "Bridge v2.14.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": (
                            "Theme directory name (key in wp_get_themes()). "
                            "Alphanumerics, dashes, underscores only."
                        ),
                    },
                },
                "required": ["slug"],
            },
            "scope": "editor",
        },
        {
            "name": "wp_theme_delete",
            "method_name": "wp_theme_delete",
            "description": (
                "Delete an installed theme by slug. Companion refuses to "
                "delete the active theme (returns ``theme_active``) and the "
                "current default theme. Caller must hold delete_themes. "
                "Requires Airano MCP Bridge v2.14.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Theme directory name to delete.",
                    },
                },
                "required": ["slug"],
            },
            "scope": "editor",
        },
        # ───── Theme file CRUD ───────────────────────────────────────
        {
            "name": "wp_theme_file_list",
            "method_name": "wp_theme_file_list",
            "description": (
                "List files inside a theme directory. Walks "
                "``wp-content/themes/{theme_slug}`` and returns each file's "
                "relative path, size, mime, sha256, and modified_at (epoch). "
                "Optional ``glob`` filters by fnmatch pattern (default "
                "``**/*``). Capped at 1000 files per call (S-18); when the "
                "walk truncates, the response carries ``truncated: true``. "
                "Requires Airano MCP Bridge v2.14.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "theme_slug": {
                        "type": "string",
                        "description": "Theme directory name (S-15).",
                    },
                    "glob": {
                        "type": "string",
                        "description": (
                            "fnmatch glob (e.g. ``**/*.php``). Defaults to "
                            "``**/*`` — every file."
                        ),
                        "default": "**/*",
                    },
                    "max_files": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _THEME_LIST_MAX_FILES,
                        "default": _THEME_LIST_MAX_FILES,
                        "description": (
                            "Hard cap on entries returned. Companion stops "
                            "the walk and sets truncated=true on overflow."
                        ),
                    },
                },
                "required": ["theme_slug"],
            },
            "scope": "read",
        },
        {
            "name": "wp_theme_file_read",
            "method_name": "wp_theme_file_read",
            "description": (
                "Read a file inside a theme as base64. Returns "
                "``{content_base64, mime, size, sha256, modified_at}``. Path "
                "must resolve under ``wp-content/themes/{theme_slug}`` "
                "(S-16); ``..``, absolute paths, null bytes, and symlinks "
                "that escape are rejected by the companion's realpath gate. "
                "Files larger than 5 MB return ``file_too_large`` (S-18). "
                "Requires Airano MCP Bridge v2.14.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "theme_slug": {"type": "string"},
                    "path": {
                        "type": "string",
                        "description": (
                            "Theme-relative path. ``style.css``, "
                            "``parts/header.html``, ``functions.php``, etc."
                        ),
                    },
                },
                "required": ["theme_slug", "path"],
            },
            "scope": "read",
        },
        {
            "name": "wp_theme_file_write",
            "method_name": "wp_theme_file_write",
            "description": (
                "Write a file inside a theme. ``content_base64`` is the "
                "decoded body (capped at 5 MB, S-18). PHP file writes "
                "additionally require ``edit_themes`` AND "
                "``!DISALLOW_FILE_EDIT`` (S-17); non-PHP writes only need "
                "``edit_themes``. Pass ``expected_sha256`` for optimistic "
                "concurrency: the companion compares against the current "
                "file's sha256 and returns ``sha_mismatch`` (409) on drift "
                "(S-19). When ``create_dirs`` is true (default) any missing "
                "parent directories are created. Requires Airano MCP Bridge "
                "v2.14.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "theme_slug": {"type": "string"},
                    "path": {"type": "string"},
                    "content_base64": {
                        "type": "string",
                        "description": (
                            "Base64-encoded file body. Decoded server-side; "
                            "5 MB hard cap (S-18)."
                        ),
                    },
                    "expected_sha256": {
                        "type": "string",
                        "description": (
                            "Optional sha256 of the on-disk file the caller "
                            "based their edit on. When supplied, companion "
                            "rejects with sha_mismatch on drift (S-19). "
                            "Omit to perform an unconditional write."
                        ),
                    },
                    "create_dirs": {
                        "type": "boolean",
                        "default": True,
                        "description": (
                            "Create any missing parent directories. Set to "
                            "false to require the directory already exists."
                        ),
                    },
                },
                "required": ["theme_slug", "path", "content_base64"],
            },
            "scope": "editor",
        },
        {
            "name": "wp_theme_file_delete",
            "method_name": "wp_theme_file_delete",
            "description": (
                "Delete a file inside a theme. Path resolution is identical "
                "to wp_theme_file_read (S-16). Refuses to delete "
                "``style.css`` of the active theme — that would break the "
                "front-end. Requires Airano MCP Bridge v2.14.0+ and "
                "``edit_themes``."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "theme_slug": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["theme_slug", "path"],
            },
            "scope": "editor",
        },
    ]


# ─────────────────────────────────────────────────────────────────────
# Client-side validation helpers
#
# These are structural guards so the obvious bad calls don't reach the
# wire. The binding security check for both rules is server-side: the
# companion canonicalises paths via ``realpath()`` (S-16) and intersects
# the slug list with ``wp_get_themes()`` (S-15).
# ─────────────────────────────────────────────────────────────────────


def _validate_theme_slug(slug: Any) -> str:
    """S-15 client-side guard.

    Reject obviously-malformed slugs before the wire. The companion
    still does the real ``wp_get_themes()`` membership check.
    """
    if not isinstance(slug, str) or not slug:
        raise ValueError("theme_slug must be a non-empty string")
    if not _THEME_SLUG_RE.match(slug):
        raise ValueError(
            f"theme_slug must be alphanumerics + dashes + underscores "
            f"(<=64 chars, no leading dash); got {slug!r}"
        )
    return slug


def _validate_theme_file_path(path: Any) -> str:
    """S-16 client-side guard.

    Reject the obvious traversal shapes — ``..`` segments, leading
    slashes, null bytes, backslashes (Windows-style escapes). The
    companion's ``realpath()`` is the binding gate.
    """
    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")
    if "\x00" in path:
        raise ValueError("path must not contain null bytes")
    if "\\" in path:
        raise ValueError("path must use forward slashes only")
    if path.startswith("/"):
        raise ValueError("path must be theme-relative (no leading slash)")
    # Reject any segment equal to ``..`` — accepts ``..foo`` (a real
    # filename) but blocks the traversal idiom.
    parts = [p for p in path.split("/") if p]
    if any(p == ".." for p in parts):
        raise ValueError("path must not contain `..` segments")
    if not parts:
        raise ValueError("path must reference a file, not the theme root")
    return "/".join(parts)


def _quote_path(path: str) -> str:
    """Percent-encode a theme-relative path while keeping ``/`` literal."""
    return quote(path, safe="/")


class ThemesHandler:
    """Theme management + theme file CRUD surface (F.19.7).

    Each method returns the parsed JSON envelope from the companion. The
    plugin.py wrapper layer is responsible for serialising the dict for
    MCP transport.
    """

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    # ── Theme management ────────────────────────────────────────────

    async def wp_theme_install_from_zip(
        self,
        zip_url: str | None = None,
        zip_base64: str | None = None,
        activate: bool = False,
        overwrite: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        # Exactly one source must be supplied — both the prompt and the
        # companion route reject the empty + double-supply cases.
        if not zip_url and not zip_base64:
            raise ValueError("wp_theme_install_from_zip requires zip_url or zip_base64")
        if zip_url and zip_base64:
            raise ValueError("wp_theme_install_from_zip accepts zip_url OR zip_base64, not both")
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
            # Cheap pre-cap: base64 expands by ~4/3, so ``len * 3 // 4``
            # is an upper bound on the decoded byte count. This catches
            # the obviously-too-big payloads without doing a full
            # decode (which would double the memory usage).
            decoded_size_upper_bound = len(zip_base64) * 3 // 4
            if decoded_size_upper_bound > _THEME_ZIP_MAX_BYTES:
                raise ValueError(
                    f"zip_base64 decodes to roughly {decoded_size_upper_bound} bytes "
                    f"— exceeds {_THEME_ZIP_MAX_BYTES} byte cap (S-18)"
                )
            body["zip_base64"] = zip_base64
        return await self.client.post(
            f"{_ADMIN_NS}/themes/install",
            json_data=body,
            use_custom_namespace=True,
        )

    async def wp_theme_activate(self, slug: str, **_: Any) -> dict[str, Any]:
        slug = _validate_theme_slug(slug)
        return await self.client.post(
            f"{_ADMIN_NS}/themes/{slug}/activate",
            json_data={},
            use_custom_namespace=True,
        )

    async def wp_theme_delete(self, slug: str, **_: Any) -> dict[str, Any]:
        slug = _validate_theme_slug(slug)
        return await self.client.delete(
            f"{_ADMIN_NS}/themes/{slug}",
            use_custom_namespace=True,
        )

    # ── Theme file CRUD ─────────────────────────────────────────────

    async def wp_theme_file_list(
        self,
        theme_slug: str,
        glob: str = "**/*",
        max_files: int = _THEME_LIST_MAX_FILES,
        **_: Any,
    ) -> dict[str, Any]:
        theme_slug = _validate_theme_slug(theme_slug)
        if not isinstance(glob, str) or not glob:
            raise ValueError("glob must be a non-empty string")
        if not isinstance(max_files, int) or isinstance(max_files, bool) or max_files <= 0:
            raise ValueError("max_files must be a positive integer")
        if max_files > _THEME_LIST_MAX_FILES:
            raise ValueError(
                f"max_files {max_files} exceeds the {_THEME_LIST_MAX_FILES} per-call cap (S-18)"
            )
        return await self.client.get(
            f"{_ADMIN_NS}/themes/files/{theme_slug}",
            params={"glob": glob, "max_files": max_files},
            use_custom_namespace=True,
        )

    async def wp_theme_file_read(
        self,
        theme_slug: str,
        path: str,
        **_: Any,
    ) -> dict[str, Any]:
        theme_slug = _validate_theme_slug(theme_slug)
        path = _validate_theme_file_path(path)
        return await self.client.get(
            f"{_ADMIN_NS}/themes/files/{theme_slug}/{_quote_path(path)}",
            use_custom_namespace=True,
        )

    async def wp_theme_file_write(
        self,
        theme_slug: str,
        path: str,
        content_base64: str,
        expected_sha256: str | None = None,
        create_dirs: bool = True,
        **_: Any,
    ) -> dict[str, Any]:
        theme_slug = _validate_theme_slug(theme_slug)
        path = _validate_theme_file_path(path)
        if not isinstance(content_base64, str):
            raise ValueError("content_base64 must be a string")
        decoded_size_upper_bound = len(content_base64) * 3 // 4
        if decoded_size_upper_bound > _THEME_FILE_MAX_BYTES:
            raise ValueError(
                f"content_base64 decodes to roughly {decoded_size_upper_bound} bytes "
                f"— exceeds {_THEME_FILE_MAX_BYTES} byte cap (S-18)"
            )
        body: dict[str, Any] = {
            "content_base64": content_base64,
            "create_dirs": bool(create_dirs),
        }
        if expected_sha256 is not None:
            if not isinstance(expected_sha256, str) or not re.fullmatch(
                r"[0-9a-fA-F]{64}", expected_sha256
            ):
                raise ValueError("expected_sha256 must be a 64-char hex string")
            body["expected_sha256"] = expected_sha256.lower()
        return await self.client.put(
            f"{_ADMIN_NS}/themes/files/{theme_slug}/{_quote_path(path)}",
            json_data=body,
            use_custom_namespace=True,
        )

    async def wp_theme_file_delete(
        self,
        theme_slug: str,
        path: str,
        **_: Any,
    ) -> dict[str, Any]:
        theme_slug = _validate_theme_slug(theme_slug)
        path = _validate_theme_file_path(path)
        return await self.client.delete(
            f"{_ADMIN_NS}/themes/files/{theme_slug}/{_quote_path(path)}",
            use_custom_namespace=True,
        )
