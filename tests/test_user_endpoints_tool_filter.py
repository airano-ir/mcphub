"""F.5a.9.x: per-site tool visibility filter for wordpress_generate_and_upload_image.

Verifies that ``_get_visible_tools_for_site`` hides the AI-image tool from
``tools/list`` when the site has no provider key configured — the user's
stated requirement that "if not defined, the image creation tool should
be disabled by default".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.user_endpoints import _get_visible_tools_for_site


def _make_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = f"description for {name}"
    tool.plugin_type = "wordpress"
    tool.required_scope = "write"
    tool.category = "write"
    tool.sensitivity = "normal"
    tool.input_schema = {"type": "object", "properties": {}}
    return tool


@pytest.fixture
def base_tools():
    return [
        _make_tool("wordpress_list_posts"),
        _make_tool("wordpress_create_post"),
        _make_tool("wordpress_generate_and_upload_image"),
    ]


class TestAIImageToolVisibility:
    @pytest.mark.unit
    async def test_no_key_hides_ai_tool(self, base_tools):
        """Site without any provider key → ai-image tool is filtered out."""
        with (
            patch("core.tool_access.get_tool_access_manager") as m_access,
            patch("core.site_api.list_site_providers_set", AsyncMock(return_value=set())),
        ):
            m_access.return_value.get_visible_tools = AsyncMock(return_value=base_tools)
            out = await _get_visible_tools_for_site(
                site_id="site-1", key_scopes=["write"], plugin_type="wordpress"
            )

        names = [t["name"] for t in out]
        assert "wordpress_generate_and_upload_image" not in names
        assert "wordpress_list_posts" in names
        assert "wordpress_create_post" in names

    @pytest.mark.unit
    async def test_any_key_exposes_ai_tool(self, base_tools):
        """Site with at least one provider key → ai-image tool is visible."""
        with (
            patch("core.tool_access.get_tool_access_manager") as m_access,
            patch(
                "core.site_api.list_site_providers_set",
                AsyncMock(return_value={"openai"}),
            ),
        ):
            m_access.return_value.get_visible_tools = AsyncMock(return_value=base_tools)
            out = await _get_visible_tools_for_site(
                site_id="site-1", key_scopes=["write"], plugin_type="wordpress"
            )

        names = [t["name"] for t in out]
        assert "wordpress_generate_and_upload_image" in names

    @pytest.mark.unit
    async def test_non_wp_wc_plugins_are_unaffected(self):
        """Gitea etc. never carry provider keys and never register the
        ai-image tool — the filter must not interfere."""
        tools = [_make_tool("gitea_list_repos")]
        tools[0].plugin_type = "gitea"

        with patch("core.tool_access.get_tool_access_manager") as m_access:
            m_access.return_value.get_visible_tools = AsyncMock(return_value=tools)
            # list_site_providers_set should NOT be called on non-wp/wc plugin types
            with patch(
                "core.site_api.list_site_providers_set",
                AsyncMock(side_effect=AssertionError("should not be called")),
            ):
                out = await _get_visible_tools_for_site(
                    site_id="site-1", key_scopes=["read"], plugin_type="gitea"
                )

        assert [t["name"] for t in out] == ["gitea_list_repos"]

    @pytest.mark.unit
    async def test_woocommerce_plugin_also_gates_ai_tool(self, base_tools):
        """Symmetric behaviour on woocommerce plugin_type."""
        with (
            patch("core.tool_access.get_tool_access_manager") as m_access,
            patch("core.site_api.list_site_providers_set", AsyncMock(return_value=set())),
        ):
            m_access.return_value.get_visible_tools = AsyncMock(return_value=base_tools)
            out = await _get_visible_tools_for_site(
                site_id="wc-1", key_scopes=["write"], plugin_type="woocommerce"
            )

        names = [t["name"] for t in out]
        assert "wordpress_generate_and_upload_image" not in names
