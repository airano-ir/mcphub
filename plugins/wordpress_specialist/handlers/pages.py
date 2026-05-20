"""F.19.5 — Page editing surface (Gutenberg + Elementor + Classic).

Eleven tools split across three surfaces. The Gutenberg + Elementor +
Classic surfaces share one handler because every tool reaches the same
WordPress site through the same companion plugin; splitting along the
"`pages.py` for content writes / `management.py` for inventory" axis
keeps each handler small and focused.

Surface map:

* **Gutenberg** (4 tools, companion v2.13.0 routes ``/admin/blocks/*``):
  ``wp_blocks_get`` reads via stock REST + ``parse_blocks()`` server-side
  in MCPHub; the writes (``wp_blocks_replace`` / ``wp_blocks_insert_at``
  / ``wp_blocks_remove_at``) hit the companion so ``serialize_blocks()``
  stays server-side and avoids client-side corruption of HTML comment
  delimiters.
* **Elementor** (6 tools, ``/admin/elementor/*``):
  ``wp_elementor_detect`` + ``wp_elementor_get`` + ``wp_elementor_template_list``
  read; ``wp_elementor_set`` + ``wp_elementor_render_css`` +
  ``wp_elementor_template_apply`` write. The companion handles the
  slash-strip / JSON-validate dance and fires
  ``elementor/document/after_save`` after writes so caches and CSS
  regenerate cleanly.
* **Classic** (1 tool): ``wp_classic_html_replace`` is a thin
  ``post_content`` swap — the only F.19.5 tool that exists for sites
  that haven't migrated to the block editor.

Security rules layered on top of F.19.2 S-1…S-11 (companion enforces
these regardless of MCPHub-side guards):

* **S-12** — every block / Elementor / Classic write requires
  ``edit_post`` on the target post id (per-item, not just the global
  manage_options gate). Companion checks via ``current_user_can``.
* **S-13** — block + classic content sanitised via ``wp_kses_post`` by
  default; ``raw_html=True`` only goes through when the calling WP user
  has ``unfiltered_html``.
* **S-14** — Elementor JSON node count capped at 5,000 per call; the
  companion returns ``elementor_too_large`` when oversized — callers
  should switch to ``wp_elementor_template_apply``.

All tools require Airano MCP Bridge v2.13.0+.
"""

from __future__ import annotations

from typing import Any

from plugins.wordpress.client import WordPressClient

# Companion admin namespace — same prefix used by the management surface.
_ADMIN_NS = "airano-mcp/v1/admin"

# Stock REST namespace — used by the two tools that don't need companion
# routes (``wp_blocks_get`` and ``wp_classic_html_replace`` read paths).
_WP_NS = "wp/v2"

# Mirrored from the companion's BLOCKS_MAX_PER_CALL / ELEMENTOR_MAX_NODES
# constants so MCPHub can reject obviously-oversized payloads before
# they reach the wire. The companion enforces the real limit.
_BLOCKS_MAX_PER_CALL = 200
_ELEMENTOR_MAX_NODES = 5000


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specs for the F.19.5 page editing surface."""
    return [
        # ───── Gutenberg blocks ──────────────────────────────────────
        {
            "name": "wp_blocks_get",
            "method_name": "wp_blocks_get",
            "description": (
                "Read a post or page as a block tree. Fetches post_content "
                "via stock REST then parses it server-side with WP's block "
                "grammar so the caller gets a structured array of "
                "{blockName, attrs, innerBlocks, innerHTML} entries. Works "
                "on any WordPress 5.0+ install — no companion route "
                "needed for reads."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Target post or page id.",
                        "minimum": 1,
                    },
                    "post_type": {
                        "type": "string",
                        "description": (
                            "Stock REST collection — ``posts`` (default) or "
                            "``pages``. Companion isn't consulted for reads."
                        ),
                        "default": "posts",
                    },
                },
                "required": ["post_id"],
            },
            "scope": "read",
        },
        {
            "name": "wp_blocks_replace",
            "method_name": "wp_blocks_replace",
            "description": (
                "Replace a post's full block tree. The companion serializes "
                "the array via WP's serialize_blocks() so HTML comment "
                "delimiters round-trip cleanly. Block content is sanitised "
                "with wp_kses_post unless raw_html=true (S-13: requires "
                "the WP user to also hold unfiltered_html). Capped at 200 "
                "blocks per call. Requires Airano MCP Bridge v2.13.0+ and "
                "edit_post on the target."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "minimum": 1},
                    "blocks": {
                        "type": "array",
                        "description": (
                            "Array of block dicts (same shape parse_blocks "
                            "returns). innerBlocks may be nested."
                        ),
                        "maxItems": _BLOCKS_MAX_PER_CALL,
                    },
                    "raw_html": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Skip wp_kses_post sanitisation. Companion "
                            "still enforces unfiltered_html — false stays "
                            "the default in every case."
                        ),
                    },
                },
                "required": ["post_id", "blocks"],
            },
            "scope": "editor",
        },
        {
            "name": "wp_blocks_insert_at",
            "method_name": "wp_blocks_insert_at",
            "description": (
                "Insert a single block at a given index, pushing the rest "
                "down. Same sanitisation + cap rules as wp_blocks_replace. "
                "Requires Airano MCP Bridge v2.13.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "minimum": 1},
                    "index": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "0-based insertion point. Pass the current "
                            "block count to append. Defaults to append."
                        ),
                    },
                    "block": {
                        "type": "object",
                        "description": "Single block dict to insert.",
                    },
                    "raw_html": {"type": "boolean", "default": False},
                },
                "required": ["post_id", "block"],
            },
            "scope": "editor",
        },
        {
            "name": "wp_blocks_remove_at",
            "method_name": "wp_blocks_remove_at",
            "description": (
                "Remove the block at the given index. The response "
                "includes the removed block so the caller can rollback by "
                "feeding it back to wp_blocks_insert_at. Requires Airano "
                "MCP Bridge v2.13.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "minimum": 1},
                    "index": {"type": "integer", "minimum": 0},
                },
                "required": ["post_id", "index"],
            },
            "scope": "editor",
        },
        # ───── Elementor ─────────────────────────────────────────────
        {
            "name": "wp_elementor_detect",
            "method_name": "wp_elementor_detect",
            "description": (
                "Report Elementor presence on the site: installed flag, "
                "version, Pro flag, and the post types Elementor edits. "
                "Returns ``installed: false`` cleanly when Elementor is "
                "absent — non-Elementor sites do not 404. Requires Airano "
                "MCP Bridge v2.13.0+."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_elementor_get",
            "method_name": "wp_elementor_get",
            "description": (
                "Fetch the parsed _elementor_data tree for a post. The "
                "companion strips WP's slashes and JSON-decodes server-"
                "side; the caller always sees a plain array. Returns "
                "``edited_with_elementor: false`` if the post hasn't been "
                "opened in Elementor. Requires Airano MCP Bridge v2.13.0+."
            ),
            "schema": {
                "type": "object",
                "properties": {"post_id": {"type": "integer", "minimum": 1}},
                "required": ["post_id"],
            },
            "scope": "read",
        },
        {
            "name": "wp_elementor_set",
            "method_name": "wp_elementor_set",
            "description": (
                "Replace a post's _elementor_data tree. Companion validates "
                "every node has id/elType/settings, enforces the 5,000-node "
                "cap (S-14), writes via update_post_meta, and fires "
                "elementor/document/after_save so caches and CSS clear. "
                "Oversized payloads return ``elementor_too_large``; switch "
                "to wp_elementor_template_apply. Requires Airano MCP "
                "Bridge v2.13.0+ and edit_post on the target."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "minimum": 1},
                    "data": {
                        "type": "array",
                        "description": (
                            "Top-level Elementor sections array. Every "
                            "node (recursively, via ``elements``) must "
                            "carry id, elType, settings."
                        ),
                    },
                },
                "required": ["post_id", "data"],
            },
            "scope": "editor",
        },
        {
            "name": "wp_elementor_render_css",
            "method_name": "wp_elementor_render_css",
            "description": (
                "Trigger Elementor's per-post CSS regeneration so the "
                "front-end picks up changes from a recent wp_elementor_set "
                "or theme switch. Equivalent to clicking 'Regenerate CSS' "
                "scoped to a single post. Requires Airano MCP Bridge "
                "v2.13.0+ and Elementor active."
            ),
            "schema": {
                "type": "object",
                "properties": {"post_id": {"type": "integer", "minimum": 1}},
                "required": ["post_id"],
            },
            "scope": "editor",
        },
        {
            "name": "wp_elementor_template_list",
            "method_name": "wp_elementor_template_list",
            "description": (
                "List saved Elementor templates (the elementor_library "
                "CPT). Returns id, title, type (page/section/header/…), "
                "and modified_gmt. Returns ``installed: false`` cleanly "
                "if Elementor is not active. Requires Airano MCP Bridge "
                "v2.13.0+."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "wp_elementor_template_apply",
            "method_name": "wp_elementor_template_apply",
            "description": (
                "Copy a saved Elementor template's data into a target "
                "post. Subject to the same S-14 5,000-node cap as "
                "wp_elementor_set. Useful when a payload exceeds the "
                "cap — clone a known-good template instead of streaming "
                "raw JSON. Requires Airano MCP Bridge v2.13.0+ and "
                "edit_post on the target."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "template_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Source elementor_library post id.",
                    },
                    "post_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Target post id (where the layout lands).",
                    },
                },
                "required": ["template_id", "post_id"],
            },
            "scope": "editor",
        },
        # ───── Classic editor ────────────────────────────────────────
        {
            "name": "wp_classic_html_replace",
            "method_name": "wp_classic_html_replace",
            "description": (
                "Pure post_content swap for sites still on the Classic "
                "editor. Companion sanitises with wp_kses_post unless "
                "raw_html=true (S-13). Requires Airano MCP Bridge "
                "v2.13.0+ and edit_post on the target."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "minimum": 1},
                    "html": {
                        "type": "string",
                        "description": "Replacement post_content body.",
                    },
                    "raw_html": {"type": "boolean", "default": False},
                },
                "required": ["post_id", "html"],
            },
            "scope": "editor",
        },
    ]


def _validate_post_id(post_id: Any) -> int:
    """Reject obviously-bad ids before the wire."""
    if not isinstance(post_id, int) or isinstance(post_id, bool) or post_id <= 0:
        raise ValueError(f"post_id must be a positive integer, got {post_id!r}")
    return post_id


def _count_elementor_nodes(tree: list[Any]) -> int:
    """Recursively count Elementor nodes (mirrors the companion's walker)."""
    total = 0
    for node in tree:
        if isinstance(node, dict):
            total += 1
            children = node.get("elements")
            if isinstance(children, list):
                total += _count_elementor_nodes(children)
    return total


class PagesHandler:
    """Block + Elementor + Classic page-editing surface (F.19.5).

    Each method returns the parsed JSON envelope from the companion (or
    from stock REST in the two read-only cases). The plugin.py wrapper
    layer is responsible for serialising the dict for MCP transport.
    """

    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    # ── Gutenberg ────────────────────────────────────────────────────

    async def wp_blocks_get(
        self,
        post_id: int,
        post_type: str = "posts",
        **_: Any,
    ) -> dict[str, Any]:
        """Read post_content via stock REST, parse blocks server-side."""
        post_id = _validate_post_id(post_id)
        if post_type not in {"posts", "pages"}:
            raise ValueError(f"post_type must be 'posts' or 'pages', got {post_type!r}")
        # Stock REST returns post_content under "content.raw" when
        # context=edit and the user has edit_posts. The wordpress
        # client always authenticates with an Application Password so
        # we ask for the raw form.
        post = await self.client.get(
            f"{post_type}/{post_id}",
            params={"context": "edit"},
        )
        raw = ""
        if isinstance(post, dict):
            content = post.get("content")
            if isinstance(content, dict):
                raw = content.get("raw") or content.get("rendered") or ""
        # Lazy import — `parse_blocks` lives in MCPHub-side helpers so
        # we don't reach into a separate WordPress installation.
        blocks = _parse_blocks_python(raw)
        return {
            "post_id": post_id,
            "post_type": post_type,
            "count": len(blocks),
            "blocks": blocks,
        }

    async def wp_blocks_replace(
        self,
        post_id: int,
        blocks: list[dict[str, Any]],
        raw_html: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        post_id = _validate_post_id(post_id)
        if not isinstance(blocks, list):
            raise ValueError("blocks must be a list of block dicts")
        if len(blocks) > _BLOCKS_MAX_PER_CALL:
            raise ValueError(f"blocks exceeds {_BLOCKS_MAX_PER_CALL} per call (got {len(blocks)})")
        return await self.client.post(
            f"{_ADMIN_NS}/blocks/replace",
            json_data={"post_id": post_id, "blocks": blocks, "raw_html": bool(raw_html)},
            use_custom_namespace=True,
        )

    async def wp_blocks_insert_at(
        self,
        post_id: int,
        block: dict[str, Any],
        index: int | None = None,
        raw_html: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        post_id = _validate_post_id(post_id)
        if not isinstance(block, dict):
            raise ValueError("block must be a dict")
        body: dict[str, Any] = {
            "post_id": post_id,
            "block": block,
            "raw_html": bool(raw_html),
        }
        if index is not None:
            if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                raise ValueError("index must be a non-negative integer")
            body["index"] = index
        return await self.client.post(
            f"{_ADMIN_NS}/blocks/insert",
            json_data=body,
            use_custom_namespace=True,
        )

    async def wp_blocks_remove_at(
        self,
        post_id: int,
        index: int,
        **_: Any,
    ) -> dict[str, Any]:
        post_id = _validate_post_id(post_id)
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("index must be a non-negative integer")
        return await self.client.post(
            f"{_ADMIN_NS}/blocks/remove",
            json_data={"post_id": post_id, "index": index},
            use_custom_namespace=True,
        )

    # ── Elementor ────────────────────────────────────────────────────

    async def wp_elementor_detect(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/elementor/status",
            use_custom_namespace=True,
        )

    async def wp_elementor_get(self, post_id: int, **_: Any) -> dict[str, Any]:
        post_id = _validate_post_id(post_id)
        return await self.client.get(
            f"{_ADMIN_NS}/elementor/{post_id}",
            use_custom_namespace=True,
        )

    async def wp_elementor_set(
        self,
        post_id: int,
        data: list[Any],
        **_: Any,
    ) -> dict[str, Any]:
        post_id = _validate_post_id(post_id)
        if not isinstance(data, list):
            raise ValueError("data must be a top-level Elementor sections array")
        node_count = _count_elementor_nodes(data)
        if node_count > _ELEMENTOR_MAX_NODES:
            raise ValueError(
                f"Elementor payload has {node_count} nodes — exceeds "
                f"{_ELEMENTOR_MAX_NODES} per call. Use "
                f"wp_elementor_template_apply with a saved template instead."
            )
        return await self.client.post(
            f"{_ADMIN_NS}/elementor/{post_id}",
            json_data={"data": data},
            use_custom_namespace=True,
        )

    async def wp_elementor_render_css(self, post_id: int, **_: Any) -> dict[str, Any]:
        post_id = _validate_post_id(post_id)
        return await self.client.post(
            f"{_ADMIN_NS}/elementor/{post_id}/regen-css",
            json_data={},
            use_custom_namespace=True,
        )

    async def wp_elementor_template_list(self, **_: Any) -> dict[str, Any]:
        return await self.client.get(
            f"{_ADMIN_NS}/elementor/templates",
            use_custom_namespace=True,
        )

    async def wp_elementor_template_apply(
        self,
        template_id: int,
        post_id: int,
        **_: Any,
    ) -> dict[str, Any]:
        post_id = _validate_post_id(post_id)
        if not isinstance(template_id, int) or isinstance(template_id, bool) or template_id <= 0:
            raise ValueError("template_id must be a positive integer")
        return await self.client.post(
            f"{_ADMIN_NS}/elementor/templates/apply",
            json_data={"template_id": template_id, "post_id": post_id},
            use_custom_namespace=True,
        )

    # ── Classic editor ───────────────────────────────────────────────

    async def wp_classic_html_replace(
        self,
        post_id: int,
        html: str,
        raw_html: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        post_id = _validate_post_id(post_id)
        if not isinstance(html, str):
            raise ValueError("html must be a string")
        return await self.client.post(
            f"{_ADMIN_NS}/classic/{post_id}/replace",
            json_data={"html": html, "raw_html": bool(raw_html)},
            use_custom_namespace=True,
        )


# ─────────────────────────────────────────────────────────────────────
# Block grammar parser (Python port)
#
# WP's grammar is documented at
# https://developer.wordpress.org/block-editor/reference-guides/data/data-core-blocks/
# but every block read operation is just round-tripping HTML comments
# of the form:
#     <!-- wp:blockname {"attr":"value"} -->
#         <p>inner html</p>
#         <!-- wp:innerName -->...<!-- /wp:innerName -->
#     <!-- /wp:blockname -->
#
# Matching the official PHP grammar exactly would require a state
# machine; the cases F.19.5 cares about are simpler — we need to
# extract the block tree shape (name + attrs + innerHTML + innerBlocks)
# so a downstream caller can reason about it. The parser below is
# intentionally narrow: it covers `parse_blocks()` output for content
# produced by the block editor itself (the only realistic input for
# read-back). For freeform / classic-editor content it falls back to a
# single ``core/freeform`` block with the original HTML.
# ─────────────────────────────────────────────────────────────────────


def _parse_blocks_python(html: str) -> list[dict[str, Any]]:
    import json
    import re

    if not html or "<!-- wp:" not in html:
        if not html:
            return []
        return [
            {
                "blockName": None,
                "attrs": {},
                "innerBlocks": [],
                "innerHTML": html,
                "innerContent": [html],
            }
        ]

    open_re = re.compile(
        r"<!--\s*wp:([a-z0-9][a-z0-9_/-]*)\s*(\{.*?\})?\s*(/)?-->",
        re.IGNORECASE | re.DOTALL,
    )
    close_re = re.compile(r"<!--\s*/wp:([a-z0-9][a-z0-9_/-]*)\s*-->", re.IGNORECASE)

    pos = 0
    length = len(html)
    blocks: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []

    def _attach(block: dict[str, Any]) -> None:
        if stack:
            stack[-1]["innerBlocks"].append(block)
        else:
            blocks.append(block)

    while pos < length:
        m_open = open_re.search(html, pos)
        m_close = close_re.search(html, pos)

        # Pick the earliest match.
        next_open = m_open.start() if m_open else length
        next_close = m_close.start() if m_close else length

        if next_open == length and next_close == length:
            # No more delimiters — flush the rest as freeform on the
            # outer level (or innerHTML of the open block).
            tail = html[pos:length]
            if tail.strip():
                if stack:
                    stack[-1]["innerHTML"] += tail
                    stack[-1]["innerContent"].append(tail)
                else:
                    blocks.append(
                        {
                            "blockName": None,
                            "attrs": {},
                            "innerBlocks": [],
                            "innerHTML": tail,
                            "innerContent": [tail],
                        }
                    )
            break

        if next_open <= next_close and m_open is not None:
            # Free text before this open tag → inherit by current parent.
            head = html[pos:next_open]
            if head:
                if stack:
                    stack[-1]["innerHTML"] += head
                    stack[-1]["innerContent"].append(head)
                else:
                    if head.strip():
                        blocks.append(
                            {
                                "blockName": None,
                                "attrs": {},
                                "innerBlocks": [],
                                "innerHTML": head,
                                "innerContent": [head],
                            }
                        )

            name = m_open.group(1)
            attrs_raw = m_open.group(2)
            self_closing = m_open.group(3) is not None
            attrs: dict[str, Any] = {}
            if attrs_raw:
                try:
                    attrs = json.loads(attrs_raw)
                except json.JSONDecodeError:
                    attrs = {"_invalid_json": attrs_raw}
            block_name = name if "/" in name else f"core/{name}"
            block = {
                "blockName": block_name,
                "attrs": attrs,
                "innerBlocks": [],
                "innerHTML": "",
                "innerContent": [],
            }
            pos = m_open.end()
            if self_closing:
                _attach(block)
            else:
                stack.append(block)
        elif m_close is not None:
            head = html[pos:next_close]
            if head and stack:
                stack[-1]["innerHTML"] += head
                stack[-1]["innerContent"].append(head)
            if stack:
                closing = stack.pop()
                _attach(closing)
            pos = m_close.end()
        else:  # pragma: no cover — guarded by the length check above
            break

    # Anything left on the stack is a mismatched open — surface it
    # rather than silently dropping content.
    while stack:
        unclosed = stack.pop()
        _attach(unclosed)

    return blocks
