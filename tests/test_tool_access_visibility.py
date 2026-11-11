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
    check_tool_prerequisites,
    get_tool_access_manager,
)


class TestProviderKeyHelpers:
    def test_ai_image_tool_requires_key(self):
        assert _tool_requires_provider_key("wordpress_generate_and_upload_image")
        assert _tool_requires_provider_key("woocommerce_generate_and_upload_image")

    def test_normal_tool_does_not_require_key(self):
        assert not _tool_requires_provider_key("wordpress_create_post")
        assert not _tool_requires_provider_key("wordpress_list_posts")

    def test_configured_helper_returns_true_for_non_ai_tools(self):
        # Non-AI tools aren't gated; they're always "configured".
        assert _tool_has_configured_provider("wordpress_create_post", set())

    def test_configured_helper_gates_ai_on_providers_set(self):
        assert not _tool_has_configured_provider("wordpress_generate_and_upload_image", set())
        assert _tool_has_configured_provider("wordpress_generate_and_upload_image", {"openrouter"})
        assert not _tool_has_configured_provider("woocommerce_generate_and_upload_image", set())
        assert _tool_has_configured_provider("woocommerce_generate_and_upload_image", {"openai"})


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


class TestCompanionRoutePrerequisites:
    def test_route_bitmap_true_allows_tool(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_cache_purge",
            probe_payload={
                "probe_available": True,
                "plugin_version": "2.18.3",
                "routes": {"cache_purge": True},
            },
            configured_providers=set(),
        )

        assert ok is True
        assert reason is None

    def test_version_fallback_allows_stale_missing_route_bitmap(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_cache_purge",
            probe_payload={
                "probe_available": True,
                "plugin_version": "2.18.3",
                "routes": {},
            },
            configured_providers=set(),
        )

        assert ok is True
        assert reason is None

    def test_version_fallback_allows_stale_false_route_bitmap(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_wp_cache_flush",
            probe_payload={
                "probe_available": True,
                "plugin_version": "2.18.3",
                "routes": {"cache_purge": False},
            },
            configured_providers=set(),
        )

        assert ok is True
        assert reason is None

    def test_route_stays_blocked_when_plugin_version_is_too_old(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_opcache_reset",
            probe_payload={
                "probe_available": True,
                "plugin_version": "2.18.3",
                "routes": {"opcache_reset": False},
            },
            configured_providers=set(),
        )

        assert ok is False
        assert reason == "companion_route"

    def test_route_stays_blocked_when_companion_probe_failed(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_cache_purge",
            probe_payload={
                "probe_available": False,
                "plugin_version": "2.18.3",
                "routes": {"cache_purge": False},
            },
            configured_providers=set(),
        )

        assert ok is False
        assert reason == "companion_route"

    def test_legacy_transient_list_uses_new_route_gate(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_wp_transient_list",
            probe_payload={
                "probe_available": True,
                "plugin_version": "2.18.5",
                "routes": {},
            },
            configured_providers=set(),
        )

        assert ok is True
        assert reason is None

    def test_legacy_db_optimize_blocked_before_companion_2185(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_wp_db_optimize",
            probe_payload={
                "probe_available": True,
                "plugin_version": "2.18.4",
                "routes": {"admin_db_optimize": False},
            },
            configured_providers=set(),
        )

        assert ok is False
        assert reason == "companion_route"

    def test_term_language_route_requires_companion_2200(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_set_term_language",
            probe_payload={
                "probe_available": True,
                "plugin_version": "2.19.0",
                "routes": {"term_language": False},
            },
            configured_providers=set(),
        )

        assert ok is False
        assert reason == "companion_route"

    def test_term_language_route_uses_2200_version_fallback(self):
        ok, reason = check_tool_prerequisites(
            "wordpress_set_term_language",
            probe_payload={
                "probe_available": True,
                "plugin_version": "2.20.0",
                "routes": {"term_language": False},
            },
            configured_providers=set(),
        )

        assert ok is True
        assert reason is None
