"""F.19.6.B — Site layout surface (menus + widgets + customizer).

Closes the Settings → Menus, Appearance → Widgets, and Customizer gaps
on ``wordpress_specialist``. Sits on the same ``settings`` tier as the
F.19.6.A site config surface — same risk class, same dashboard preset,
no new tier this round.

Surface map:

* **Menus** (3 tools, ``/admin/menus``):
  ``wp_menu_list`` enumerates every nav menu with its theme-location
  bindings + item count. ``wp_menu_get`` reads one menu's items.
  ``wp_menu_set`` does a full-replace write — items not in the array
  are deleted, new items are created, existing items (matched by id)
  are updated. Slug stays frozen so ``theme_location`` mapping survives.

* **Widgets** (3 tools, ``/admin/widgets/*``):
  ``wp_widget_areas_list`` enumerates registered sidebar areas with
  their kind (``block`` or ``legacy``). ``wp_widget_get`` reads one
  area; block-kind areas return parsed block trees + raw HTML for
  roundtrip, legacy-kind areas return option-keyed settings.
  ``wp_widget_set`` does a full-replace write — block areas accept any
  block raw HTML; legacy areas accept ``text`` widget settings only
  this round (other legacy types are read-only).

* **Customizer** (1 tool, ``/admin/customizer/changeset``):
  ``wp_customizer_changeset`` wraps the customizer changeset queue with
  a single action enum (``get`` / ``apply`` / ``discard``). Lower
  priority — most modern themes use the FSE site editor instead of the
  customizer.

Security rules (extending S-1…S-21):

* **S-22** — Nav-menu items reference posts/terms via ``object_id``.
  Companion dispatches by item ``type``: ``post_type`` checks
  ``read_post`` meta cap; ``taxonomy`` allows public taxonomies and
  otherwise requires the taxonomy's ``assign_terms`` cap (deliberately
  NOT ``manage_categories`` — that's a write cap and would refuse
  routine "add public Category X to footer" flows for editors who
  don't manage taxonomies); ``custom`` URL items skip the object check.
  Refusals surface as ``forbidden_object_id`` 403/404.
* **S-23** — Widget HTML (block ``content`` and legacy ``text.text``)
  is sanitised via ``wp_kses_post`` unless the caller has
  ``unfiltered_html``. Mirrors S-13 from F.19.5.
* **S-24** — Customizer ``apply`` requires the caller to also hold
  ``customize`` (the cap WP uses for ``/wp-admin/customize.php``).
  ``manage_options`` alone is not enough — same as the WP UI. ``get``
  and ``discard`` only need ``manage_options``.

All tools require Airano MCP Bridge v2.17.0+.
"""

from __future__ import annotations

from typing import Any

from plugins.wordpress.client import WordPressClient

# Companion admin namespace — same prefix used by every F.19.* surface.
_ADMIN_NS = "airano-mcp/v1/admin"

# Nav-menu item types WP recognises. Anything else is rejected client-side
# as a cheap pre-check — the companion's S-22 dispatcher is the binding gate.
_MENU_ITEM_TYPES = {"post_type", "taxonomy", "custom"}

# Customizer changeset actions.
_CUSTOMIZER_ACTIONS = {"get", "apply", "discard"}


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for the F.19.6.B site layout surface."""
    return [
        # ───── Menus (3) ─────────────────────────────────────────────
        {
            "name": "wp_menu_list",
            "method_name": "wp_menu_list",
            "description": (
                "List every WordPress nav-menu with id / name / slug, "
                "the theme locations bound to it, and the item count. "
                "Use to discover menu_id before calling wp_menu_get / "
                "wp_menu_set. Requires Airano MCP Bridge v2.17.0+ and "
                "manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_menu_get",
            "method_name": "wp_menu_get",
            "description": (
                "Read a single nav-menu's items. Returns "
                "``{id, name, slug, items: [{id, title, type, object, "
                "object_id, parent, order, url, target, classes, xfn}]}``. "
                "``type`` is one of ``post_type`` / ``taxonomy`` / "
                "``custom``. Requires Airano MCP Bridge v2.17.0+ and "
                "manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "menu_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Menu term id (from wp_menu_list).",
                    },
                },
                "required": ["menu_id"],
            },
            "scope": "read",
        },
        {
            "name": "wp_menu_set",
            "method_name": "wp_menu_set",
            "description": (
                "Full-replace a nav-menu's items. Pass the complete "
                "items array — items not in the array are deleted, new "
                "items are created (omit ``id`` or set it to 0), "
                "existing items (matched by ``id``) are updated. Slug "
                "stays frozen so the theme_location mapping survives. "
                "Optional ``name`` renames the menu. S-22: each item's "
                "``object_id`` is validated against the caller's read "
                "permissions — ``post_type`` items require ``read_post`` "
                "on the target; non-public ``taxonomy`` items require "
                "the taxonomy's ``assign_terms`` cap; ``custom`` URL "
                "items skip the object check. Validation runs across "
                "every item before any mutation, so a refusal mid-array "
                "leaves the menu untouched. Requires Airano MCP Bridge "
                "v2.17.0+ and manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "menu_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Menu term id to overwrite.",
                    },
                    "items": {
                        "type": "array",
                        "description": "Full menu items array.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "integer",
                                    "description": (
                                        "Existing item id to update; "
                                        "omit or 0 to create a new item."
                                    ),
                                },
                                "title": {"type": "string"},
                                "type": {
                                    "type": "string",
                                    "enum": ["post_type", "taxonomy", "custom"],
                                },
                                "object": {
                                    "type": "string",
                                    "description": (
                                        "post_type slug for ``post_type`` "
                                        "items, taxonomy slug for "
                                        "``taxonomy`` items; ignored for "
                                        "``custom``."
                                    ),
                                },
                                "object_id": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": (
                                        "Referenced post / term id; " "omit for ``custom`` items."
                                    ),
                                },
                                "parent": {"type": "integer", "minimum": 0},
                                "order": {"type": "integer", "minimum": 0},
                                "url": {
                                    "type": "string",
                                    "description": (
                                        "URL for ``custom`` items; "
                                        "ignored for post_type / taxonomy."
                                    ),
                                },
                                "target": {"type": "string"},
                            },
                        },
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional rename. Slug stays frozen.",
                    },
                },
                "required": ["menu_id", "items"],
            },
            "scope": "settings",
        },
        # ───── Widgets (3) ───────────────────────────────────────────
        {
            "name": "wp_widget_areas_list",
            "method_name": "wp_widget_areas_list",
            "description": (
                "List every registered sidebar / widget area with id, "
                "name, theme_location, widget_count, and kind "
                "(``block`` or ``legacy``). Block areas store widgets "
                "as block instances; legacy areas use per-widget option "
                "keys. Requires Airano MCP Bridge v2.17.0+ and "
                "manage_options."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_widget_get",
            "method_name": "wp_widget_get",
            "description": (
                "Read one widget area's contents. Returns "
                "``{area_id, kind, widgets: [...]}``. For ``block`` "
                "kind, each widget is "
                "``{id, type:'block', blocks:[...parsed], raw:'<!-- wp:... -->'}`` "
                "— ``raw`` is the round-trippable HTML; ``blocks`` is "
                "the parsed tree for inspection. For ``legacy`` kind, "
                "each widget is "
                "``{id, type, settings:{...}}`` keyed by the widget's "
                "option store. Requires Airano MCP Bridge v2.17.0+ and "
                "manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "area_id": {
                        "type": "string",
                        "description": "Sidebar id (from wp_widget_areas_list).",
                    },
                },
                "required": ["area_id"],
            },
            "scope": "read",
        },
        {
            "name": "wp_widget_set",
            "method_name": "wp_widget_set",
            "description": (
                "Full-replace a widget area's contents. Block-kind "
                "areas accept any widget with ``raw`` (block HTML) or "
                "``blocks`` (block tree, server serialises). Legacy "
                "areas accept ``text`` widget settings only this round "
                "— other legacy widget types remain read-only. Caller-"
                "side ``kind`` is ignored: area kind is determined by "
                "the area itself; block↔legacy conversion is a theme-"
                "level decision, not an MCP one. S-23: HTML payloads "
                "are sanitised via ``wp_kses_post`` unless the caller "
                "has ``unfiltered_html``. Requires Airano MCP Bridge "
                "v2.17.0+ and manage_options."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "area_id": {"type": "string"},
                    "widgets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "description": (
                                        "``block`` for block-kind " "areas; ``text`` for legacy."
                                    ),
                                },
                                "raw": {
                                    "type": "string",
                                    "description": ("Block HTML (block kind only)."),
                                },
                                "blocks": {
                                    "type": "array",
                                    "description": (
                                        "Parsed block tree (block kind "
                                        "only); used when ``raw`` is "
                                        "absent."
                                    ),
                                },
                                "settings": {
                                    "type": "object",
                                    "description": (
                                        "Widget settings (legacy kind). "
                                        "For ``text`` widgets: "
                                        "{title, text, filter?, visual?}."
                                    ),
                                },
                            },
                        },
                    },
                },
                "required": ["area_id", "widgets"],
            },
            "scope": "settings",
        },
        # ───── Customizer (1) ────────────────────────────────────────
        {
            "name": "wp_customizer_changeset",
            "method_name": "wp_customizer_changeset",
            "description": (
                "Inspect or commit the pending customizer changeset. "
                "``action='get'`` returns the pending changeset payload "
                "(or ``{status:'empty'}`` when nothing is queued). "
                "``action='apply'`` publishes it; ``action='discard'`` "
                "trashes it. S-24: ``apply`` requires the caller to "
                "also hold the ``customize`` cap (same bar as "
                "``/wp-admin/customize.php``); ``manage_options`` alone "
                "is not enough. Apply is racy with concurrent edits "
                "via the customizer UI — this is intentional and "
                "mirrors WP's own behaviour. Requires Airano MCP "
                "Bridge v2.17.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get", "apply", "discard"],
                    },
                },
                "required": ["action"],
            },
            "scope": "settings",
        },
    ]


# ─────────────────────────────────────────────────────────────────────
# Client-side validation helpers
# ─────────────────────────────────────────────────────────────────────


def _validate_post_id(value: Any, field: str) -> int:
    """Validate a post / term id reference.

    Sibling to ``site_config._validate_attachment_id`` — separate so the
    misnaming in F.19.6.A doesn't propagate. Both are non-negative-int
    pre-checks; the binding existence + capability gate lives server-side
    in the companion (S-22 dispatcher for menus, attachment lookup for
    site identity).
    """
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer (got {value!r})")
    return value


def _validate_menu_item(item: Any, idx: int) -> dict[str, Any]:
    """Cheap structural pre-check for a nav-menu item.

    The S-22 capability dispatch is server-side; this only catches
    obvious shape errors so the caller gets fast feedback without a
    round-trip. ``custom`` items skip the ``object_id`` check (URL is
    sanitised by the companion via ``esc_url_raw``).
    """
    if not isinstance(item, dict):
        raise ValueError(f"items[{idx}] must be an object")
    item_type = item.get("type", "custom")
    if item_type not in _MENU_ITEM_TYPES:
        raise ValueError(
            f"items[{idx}].type must be one of {sorted(_MENU_ITEM_TYPES)} " f"(got {item_type!r})"
        )
    if item_type != "custom":
        # post_type + taxonomy require an object_id.
        object_id = item.get("object_id", 0)
        _validate_post_id(object_id, f"items[{idx}].object_id")
        if object_id == 0:
            raise ValueError(f"items[{idx}].object_id is required for {item_type} items")
    return item


class SiteLayoutHandler:
    """Site layout surface (F.19.6.B) — menus + widgets + customizer.

    Each method returns the parsed JSON envelope from the companion.
    The plugin.py wrapper serialises for MCP transport. Server errors
    (403 forbidden_object_id, 400 invalid_action, etc.) are relayed
    untouched — the companion is the binding gate.
    """

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    # ── Menus ───────────────────────────────────────────────────────

    async def wp_menu_list(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/menus",
            use_custom_namespace=True,
        )

    async def wp_menu_get(self, menu_id: int, **_: Any) -> dict[str, Any]:
        _validate_post_id(menu_id, "menu_id")
        if menu_id == 0:
            raise ValueError("menu_id is required (got 0)")
        return await self.client.get(
            f"{_ADMIN_NS}/menus/{menu_id}",
            use_custom_namespace=True,
        )

    async def wp_menu_set(
        self,
        menu_id: int,
        items: list[dict[str, Any]],
        name: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        _validate_post_id(menu_id, "menu_id")
        if menu_id == 0:
            raise ValueError("menu_id is required (got 0)")
        if not isinstance(items, list):
            raise ValueError("items must be a list")
        for idx, item in enumerate(items):
            _validate_menu_item(item, idx)
        body: dict[str, Any] = {"items": items}
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("name must be a non-empty string")
            body["name"] = name
        return await self.client.put(
            f"{_ADMIN_NS}/menus/{menu_id}",
            json_data=body,
            use_custom_namespace=True,
        )

    # ── Widgets ─────────────────────────────────────────────────────

    async def wp_widget_areas_list(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/widgets/areas",
            use_custom_namespace=True,
        )

    async def wp_widget_get(self, area_id: str, **_: Any) -> dict[str, Any]:
        if not isinstance(area_id, str) or not area_id:
            raise ValueError("area_id must be a non-empty string")
        return await self.client.get(
            f"{_ADMIN_NS}/widgets/{area_id}",
            use_custom_namespace=True,
        )

    async def wp_widget_set(
        self,
        area_id: str,
        widgets: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(area_id, str) or not area_id:
            raise ValueError("area_id must be a non-empty string")
        if not isinstance(widgets, list):
            raise ValueError("widgets must be a list")
        # Strip caller-side ``kind`` if present — area kind is determined
        # by the area itself, not the request. Block↔legacy conversion
        # is a theme-level decision.
        cleaned: list[dict[str, Any]] = []
        for idx, w in enumerate(widgets):
            if not isinstance(w, dict):
                raise ValueError(f"widgets[{idx}] must be an object")
            cleaned.append({k: v for k, v in w.items() if k != "kind"})
        body = {"widgets": cleaned}
        return await self.client.put(
            f"{_ADMIN_NS}/widgets/{area_id}",
            json_data=body,
            use_custom_namespace=True,
        )

    # ── Customizer ──────────────────────────────────────────────────

    async def wp_customizer_changeset(
        self,
        action: str,
        **_: Any,
    ) -> dict[str, Any]:
        if action not in _CUSTOMIZER_ACTIONS:
            raise ValueError(
                f"action must be one of {sorted(_CUSTOMIZER_ACTIONS)} " f"(got {action!r})"
            )
        return await self.client.post(
            f"{_ADMIN_NS}/customizer/changeset",
            json_data={"action": action},
            use_custom_namespace=True,
        )
