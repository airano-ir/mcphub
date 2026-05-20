"""F.19.5 — Tests for the WordPress Specialist page-editing handler.

Mocks ``WordPressClient.get`` and ``WordPressClient.post`` and asserts:

* tool spec contract: 11 tools in three buckets (4 Gutenberg + 6 Elementor
  + 1 Classic), with reads at ``scope=read`` and writes at ``scope=editor``
* each handler method targets the correct ``airano-mcp/v1/admin/*``
  route (or stock ``wp/v2/{type}/{id}``) with ``use_custom_namespace``
  set correctly
* client-side guards reject obviously-bad input (negative post_id,
  oversized block array, oversized Elementor tree) before the wire
* ``wp_blocks_get`` runs the block parser server-side in MCPHub —
  no companion route is consulted on reads
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.client import WordPressClient
from plugins.wordpress_specialist.handlers.pages import (
    PagesHandler,
    _count_elementor_nodes,
    _parse_blocks_python,
    get_tool_specifications,
)

# ───── Tool spec contract ────────────────────────────────────────────


def test_tool_specs_count_and_names_match_f195():
    specs = get_tool_specifications()
    assert len(specs) == 11, "F.19.5 advertises 4 Gutenberg + 6 Elementor + 1 Classic"
    names = {s["name"] for s in specs}
    assert names == {
        # Gutenberg
        "wp_blocks_get",
        "wp_blocks_replace",
        "wp_blocks_insert_at",
        "wp_blocks_remove_at",
        # Elementor
        "wp_elementor_detect",
        "wp_elementor_get",
        "wp_elementor_set",
        "wp_elementor_render_css",
        "wp_elementor_template_list",
        "wp_elementor_template_apply",
        # Classic
        "wp_classic_html_replace",
    }


def test_reads_are_read_scope_writes_are_editor_scope():
    specs_by_name = {s["name"]: s for s in get_tool_specifications()}
    expected_scope = {
        "wp_blocks_get": "read",
        "wp_blocks_replace": "editor",
        "wp_blocks_insert_at": "editor",
        "wp_blocks_remove_at": "editor",
        "wp_elementor_detect": "read",
        "wp_elementor_get": "read",
        "wp_elementor_set": "editor",
        "wp_elementor_render_css": "editor",
        "wp_elementor_template_list": "read",
        "wp_elementor_template_apply": "editor",
        "wp_classic_html_replace": "editor",
    }
    for name, scope in expected_scope.items():
        assert specs_by_name[name]["scope"] == scope, f"{name} should be scope={scope}"


def test_every_spec_has_the_full_contract():
    """Each F.19.5 spec must carry name, method_name, description, schema."""
    for spec in get_tool_specifications():
        assert spec["name"] == spec["method_name"]
        assert spec["description"]
        assert isinstance(spec["schema"], dict)
        assert spec["schema"].get("type") == "object"


def test_blocks_replace_schema_caps_at_200():
    spec = next(s for s in get_tool_specifications() if s["name"] == "wp_blocks_replace")
    assert spec["schema"]["properties"]["blocks"]["maxItems"] == 200


# ───── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    c = WordPressClient(site_url="https://wp.example.com", username="u", app_password="p")
    c.get = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    c.post = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    return c


@pytest.fixture
def handler(client):
    return PagesHandler(client)


# ───── Gutenberg routing ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wp_blocks_get_reads_via_stock_rest_no_companion(handler, client):
    """Reads MUST go through stock REST so non-companion sites work."""
    client.get = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "id": 42,
            "content": {
                "raw": ("<!-- wp:paragraph -->\n<p>Hello world.</p>\n<!-- /wp:paragraph -->"),
                "rendered": "<p>Hello world.</p>",
            },
        }
    )
    handler.client = client

    result = await handler.wp_blocks_get(post_id=42)

    client.get.assert_awaited_once_with("posts/42", params={"context": "edit"})
    assert result["post_id"] == 42
    assert result["count"] == 1
    assert result["blocks"][0]["blockName"] == "core/paragraph"


@pytest.mark.asyncio
async def test_wp_blocks_get_supports_pages_collection(handler, client):
    client.get = AsyncMock(return_value={"content": {"raw": ""}})  # type: ignore[method-assign]
    handler.client = client
    await handler.wp_blocks_get(post_id=12, post_type="pages")
    client.get.assert_awaited_once_with("pages/12", params={"context": "edit"})


@pytest.mark.asyncio
async def test_wp_blocks_get_rejects_bogus_post_type(handler):
    with pytest.raises(ValueError, match="post_type"):
        await handler.wp_blocks_get(post_id=1, post_type="products")


@pytest.mark.asyncio
async def test_wp_blocks_replace_calls_companion_route(handler, client):
    blocks = [
        {
            "blockName": "core/paragraph",
            "attrs": {},
            "innerBlocks": [],
            "innerHTML": "<p>hi</p>",
            "innerContent": ["<p>hi</p>"],
        }
    ]
    await handler.wp_blocks_replace(post_id=7, blocks=blocks)
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/blocks/replace",
        json_data={"post_id": 7, "blocks": blocks, "raw_html": False},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_wp_blocks_replace_rejects_oversized_payload(handler, client):
    too_many = [{"blockName": "core/paragraph"} for _ in range(201)]
    with pytest.raises(ValueError, match="exceeds 200"):
        await handler.wp_blocks_replace(post_id=1, blocks=too_many)
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_wp_blocks_replace_passes_raw_html_flag_when_true(handler, client):
    await handler.wp_blocks_replace(post_id=1, blocks=[], raw_html=True)
    args, kwargs = client.post.call_args
    assert kwargs["json_data"]["raw_html"] is True


@pytest.mark.asyncio
async def test_wp_blocks_insert_at_passes_index(handler, client):
    await handler.wp_blocks_insert_at(post_id=3, block={"blockName": "core/paragraph"}, index=2)
    args, kwargs = client.post.call_args
    assert args[0] == "airano-mcp/v1/admin/blocks/insert"
    assert kwargs["json_data"]["index"] == 2


@pytest.mark.asyncio
async def test_wp_blocks_insert_at_omits_index_when_unset(handler, client):
    await handler.wp_blocks_insert_at(post_id=3, block={"blockName": "core/paragraph"})
    args, kwargs = client.post.call_args
    assert "index" not in kwargs["json_data"], "missing index → companion appends"


@pytest.mark.asyncio
async def test_wp_blocks_remove_at_calls_remove_route(handler, client):
    await handler.wp_blocks_remove_at(post_id=3, index=1)
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/blocks/remove",
        json_data={"post_id": 3, "index": 1},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", [0, -1, "1", 1.5, True])
async def test_block_writes_reject_bad_post_id(handler, client, bad_id):
    with pytest.raises(ValueError):
        await handler.wp_blocks_replace(post_id=bad_id, blocks=[])
    client.post.assert_not_awaited()


# ───── Elementor routing ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wp_elementor_detect_calls_status_route(handler, client):
    await handler.wp_elementor_detect()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/elementor/status", use_custom_namespace=True
    )


@pytest.mark.asyncio
async def test_wp_elementor_get_calls_per_post_route(handler, client):
    await handler.wp_elementor_get(post_id=99)
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/elementor/99", use_custom_namespace=True
    )


@pytest.mark.asyncio
async def test_wp_elementor_set_posts_data_array(handler, client):
    data = [{"id": "abc", "elType": "section", "settings": {}, "elements": []}]
    await handler.wp_elementor_set(post_id=99, data=data)
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/elementor/99",
        json_data={"data": data},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_wp_elementor_set_rejects_oversized_tree_before_wire(handler, client):
    """S-14 — the companion enforces 5,000 nodes; mirror in MCPHub."""

    def _make_tree(width: int):
        return [
            {"id": str(i), "elType": "section", "settings": {}, "elements": []}
            for i in range(width)
        ]

    too_many = _make_tree(5001)
    with pytest.raises(ValueError, match="exceeds 5000"):
        await handler.wp_elementor_set(post_id=1, data=too_many)
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_wp_elementor_render_css_calls_regen_route(handler, client):
    await handler.wp_elementor_render_css(post_id=12)
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/elementor/12/regen-css",
        json_data={},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_wp_elementor_template_list_calls_templates_route(handler, client):
    await handler.wp_elementor_template_list()
    client.get.assert_awaited_once_with(
        "airano-mcp/v1/admin/elementor/templates", use_custom_namespace=True
    )


@pytest.mark.asyncio
async def test_wp_elementor_template_apply_passes_both_ids(handler, client):
    await handler.wp_elementor_template_apply(template_id=1, post_id=2)
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/elementor/templates/apply",
        json_data={"template_id": 1, "post_id": 2},
        use_custom_namespace=True,
    )


# ───── Classic routing ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wp_classic_html_replace_calls_classic_route(handler, client):
    await handler.wp_classic_html_replace(post_id=5, html="<p>x</p>")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/admin/classic/5/replace",
        json_data={"html": "<p>x</p>", "raw_html": False},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_wp_classic_html_replace_rejects_non_string_html(handler, client):
    with pytest.raises(ValueError, match="html must be a string"):
        await handler.wp_classic_html_replace(post_id=5, html=42)  # type: ignore[arg-type]
    client.post.assert_not_awaited()


# ───── Block parser ──────────────────────────────────────────────────


def test_parse_blocks_handles_empty_string():
    assert _parse_blocks_python("") == []


def test_parse_blocks_returns_freeform_for_classic_html():
    blocks = _parse_blocks_python("<p>Pre-block-editor content</p>")
    assert len(blocks) == 1
    assert blocks[0]["blockName"] is None
    assert blocks[0]["innerHTML"] == "<p>Pre-block-editor content</p>"


def test_parse_blocks_extracts_top_level_paragraph():
    html = "<!-- wp:paragraph -->\n" "<p>Hello world.</p>\n" "<!-- /wp:paragraph -->"
    blocks = _parse_blocks_python(html)
    assert len(blocks) == 1
    assert blocks[0]["blockName"] == "core/paragraph"
    assert "Hello world" in blocks[0]["innerHTML"]


def test_parse_blocks_decodes_attributes_json():
    html = '<!-- wp:heading {"level":3} -->\n' "<h3>Title</h3>\n" "<!-- /wp:heading -->"
    blocks = _parse_blocks_python(html)
    assert blocks[0]["attrs"] == {"level": 3}


def test_parse_blocks_handles_nested_blocks():
    html = (
        "<!-- wp:group -->\n"
        '<div class="wp-block-group">\n'
        "<!-- wp:paragraph -->\n"
        "<p>Inner.</p>\n"
        "<!-- /wp:paragraph -->\n"
        "</div>\n"
        "<!-- /wp:group -->"
    )
    blocks = _parse_blocks_python(html)
    assert len(blocks) == 1
    assert blocks[0]["blockName"] == "core/group"
    assert len(blocks[0]["innerBlocks"]) == 1
    assert blocks[0]["innerBlocks"][0]["blockName"] == "core/paragraph"


def test_parse_blocks_handles_self_closing_block():
    html = "<!-- wp:separator /-->"
    blocks = _parse_blocks_python(html)
    assert len(blocks) == 1
    assert blocks[0]["blockName"] == "core/separator"
    assert blocks[0]["innerBlocks"] == []


# ───── Node counter ──────────────────────────────────────────────────


def test_count_elementor_nodes_walks_recursively():
    tree = [
        {
            "id": "a",
            "elType": "section",
            "settings": {},
            "elements": [
                {
                    "id": "b",
                    "elType": "column",
                    "settings": {},
                    "elements": [{"id": "c", "elType": "widget", "settings": {}}],
                }
            ],
        },
        {"id": "d", "elType": "section", "settings": {}, "elements": []},
    ]
    assert _count_elementor_nodes(tree) == 4


# ───── Plugin-level wiring ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_plugin_returns_combined_specs_count():
    """The wordpress_specialist plugin must merge management + pages."""
    from plugins.wordpress_specialist import WordPressSpecialistPlugin

    specs = WordPressSpecialistPlugin.get_tool_specifications()
    assert len(specs) == 51, (
        "9 management + 11 page + 7 theme + 6 plugin-write + "
        "6 site-config + 7 site-layout + 3 db + 2 bulk tools"
    )


@pytest.mark.asyncio
async def test_plugin_serialises_handler_response_to_json():
    """plugin.py wraps each handler response in json.dumps(..., indent=2)."""
    from plugins.wordpress_specialist import WordPressSpecialistPlugin

    plugin = WordPressSpecialistPlugin(
        config={"url": "https://wp.example.com", "username": "u", "app_password": "p"},
    )
    plugin.pages.client.get = AsyncMock(  # type: ignore[method-assign]
        return_value={"installed": False, "version": None, "pro": False, "post_types": []}
    )
    serialised = await plugin.wp_elementor_detect()
    assert isinstance(serialised, str)
    assert json.loads(serialised) == {
        "installed": False,
        "version": None,
        "pro": False,
        "post_types": [],
    }
