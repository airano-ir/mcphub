"""F.X.fix #8 — Tool Access hides AI tools until a provider key is set.

Regression: ``wordpress_generate_and_upload_image`` appeared as
available in the Tool Access list even when the site had no AI
provider key configured. User only discovered at call time via
``NO_PROVIDER_KEY``. Fix: each tool row now carries
``provider_key_required`` + ``provider_key_configured`` so the
template can gray the tool out and render a "Configure key" CTA.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.tool_access import (
    _tool_has_configured_provider,
    _tool_requires_provider_key,
    get_tool_access_manager,
)


class TestProviderKeyHelpers:
    def test_ai_image_tool_requires_key(self):
        assert _tool_requires_provider_key("wordpress_generate_and_upload_image")

    def test_normal_tool_does_not_require_key(self):
        assert not _tool_requires_provider_key("wordpress_create_post")
        assert not _tool_requires_provider_key("wordpress_list_posts")

    def test_configured_helper_returns_true_for_non_ai_tools(self):
        # Non-AI tools aren't gated; they're always "configured".
        assert _tool_has_configured_provider("wordpress_create_post", set())

    def test_configured_helper_gates_ai_on_providers_set(self):
        assert not _tool_has_configured_provider("wordpress_generate_and_upload_image", set())
        assert _tool_has_configured_provider("wordpress_generate_and_upload_image", {"openrouter"})


class _FakeToolDef:
    """Minimal ToolDefinition stand-in for the registry mock."""

    def __init__(self, name: str, category: str = "content"):
        self.name = name
        self.description = f"desc for {name}"
        self.plugin_type = "wordpress"
        self.category = category
        self.sensitivity = "low"
        self.required_scope = "read"


class TestListToolsForSiteAnnotatesProviderKey:
    @pytest.fixture
    def fake_tools(self):
        return [
            _FakeToolDef("wordpress_list_posts"),
            _FakeToolDef("wordpress_create_post", category="content"),
            _FakeToolDef("wordpress_generate_and_upload_image", category="media"),
        ]

    @pytest.mark.asyncio
    async def test_ai_tool_flagged_not_configured_when_site_has_no_keys(self, fake_tools):
        manager = get_tool_access_manager()
        fake_db = AsyncMock()
        fake_db.get_site_tool_toggles = AsyncMock(return_value={})
        fake_registry = AsyncMock()
        fake_registry.get_by_plugin_type = lambda plugin_type: fake_tools
        with (
            patch("core.database.get_database", return_value=fake_db),
            patch("core.tool_registry.get_tool_registry", return_value=fake_registry),
            patch("core.site_api.list_site_providers_set", new=AsyncMock(return_value=set())),
        ):
            rows = await manager.list_tools_for_site("site-1", "wordpress")

        ai = next(r for r in rows if r["name"] == "wordpress_generate_and_upload_image")
        assert ai["provider_key_required"] is True
        assert ai["provider_key_configured"] is False

    @pytest.mark.asyncio
    async def test_ai_tool_flagged_configured_when_site_has_openrouter_key(self, fake_tools):
        manager = get_tool_access_manager()
        fake_db = AsyncMock()
        fake_db.get_site_tool_toggles = AsyncMock(return_value={})
        fake_registry = AsyncMock()
        fake_registry.get_by_plugin_type = lambda plugin_type: fake_tools
        with (
            patch("core.database.get_database", return_value=fake_db),
            patch("core.tool_registry.get_tool_registry", return_value=fake_registry),
            patch(
                "core.site_api.list_site_providers_set",
                new=AsyncMock(return_value={"openrouter"}),
            ),
        ):
            rows = await manager.list_tools_for_site("site-1", "wordpress")

        ai = next(r for r in rows if r["name"] == "wordpress_generate_and_upload_image")
        assert ai["provider_key_required"] is True
        assert ai["provider_key_configured"] is True

    @pytest.mark.asyncio
    async def test_non_ai_tool_always_shows_configured_regardless_of_keys(self, fake_tools):
        manager = get_tool_access_manager()
        fake_db = AsyncMock()
        fake_db.get_site_tool_toggles = AsyncMock(return_value={})
        fake_registry = AsyncMock()
        fake_registry.get_by_plugin_type = lambda plugin_type: fake_tools
        with (
            patch("core.database.get_database", return_value=fake_db),
            patch("core.tool_registry.get_tool_registry", return_value=fake_registry),
            patch("core.site_api.list_site_providers_set", new=AsyncMock(return_value=set())),
        ):
            rows = await manager.list_tools_for_site("site-1", "wordpress")

        non_ai = next(r for r in rows if r["name"] == "wordpress_create_post")
        assert non_ai["provider_key_required"] is False
        assert non_ai["provider_key_configured"] is True
