"""Tests for MCP service pages (Phase F.3)."""

from core.dashboard.routes import get_service_page_data


class TestServicePageData:
    async def test_wordpress_service_data(self):
        data = await get_service_page_data("wordpress")
        assert data is not None
        assert data["plugin_type"] == "wordpress"
        assert data["display_name"] == "WordPress"
        assert "tools" in data
        assert len(data["tools"]) > 0
        assert "credential_fields" in data

    async def test_supabase_service_data(self):
        data = await get_service_page_data("supabase")
        assert data is not None
        assert data["display_name"] == "Supabase"

    async def test_unknown_plugin_returns_none(self):
        data = await get_service_page_data("nonexistent")
        assert data is None

    async def test_tools_have_name_and_description(self):
        data = await get_service_page_data("wordpress")
        for tool in data["tools"]:
            assert "name" in tool
            assert "description" in tool

    async def test_tools_have_scope(self):
        data = await get_service_page_data("wordpress")
        for tool in data["tools"]:
            assert "scope" in tool
            assert tool["scope"] in ("read", "write", "admin")
