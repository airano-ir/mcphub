"""Tests for site-scoped tool visibility & per-site toggles (F.7b).

Covers:
    * ``ToolDefinition`` backward-compatible defaults
    * ``ToolAccessManager.apply_scope_filter`` for each scope
    * Per-site toggle filtering
    * Site-level ``tool_scope`` preset as a second restrictive layer
    * ``bulk_toggle_by_scope`` scoped to a single plugin
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

import pytest

import core.database as db_module
import core.tool_access as tool_access_module
import core.tool_registry as tool_registry_module
from core.database import Database
from core.tool_access import (
    SCOPE_TO_CATEGORIES,
    ToolAccessManager,
    scopes_to_categories,
)
from core.tool_registry import ToolDefinition, ToolRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


async def _noop_handler(**_kwargs):
    return "ok"


def _make_tool(name: str, category: str = "read", plugin_type: str = "coolify") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"desc {name}",
        input_schema={"type": "object", "properties": {}},
        handler=_noop_handler,
        required_scope="read",
        plugin_type=plugin_type,
        category=category,
    )


_SAMPLE_TOOLS: list[ToolDefinition] = [
    _make_tool("coolify_list_applications", "read"),
    _make_tool("coolify_get_application_logs", "read_sensitive"),
    _make_tool("coolify_start_application", "lifecycle"),
    _make_tool("coolify_stop_application", "lifecycle"),
    _make_tool("coolify_create_application_public", "crud"),
    _make_tool("coolify_create_application_env", "env"),
    _make_tool("coolify_get_database_backups", "backup"),
    _make_tool("coolify_delete_server", "system"),
    # Legacy plugin tool without a category annotation (defaults to "read").
    _make_tool("wordpress_list_posts", "read", plugin_type="wordpress"),
]


@pytest.fixture
def fresh_registry(monkeypatch) -> Generator[ToolRegistry, None, None]:
    """Install a clean ToolRegistry populated with _SAMPLE_TOOLS."""
    registry = ToolRegistry()
    for tool in _SAMPLE_TOOLS:
        registry.register(tool)
    monkeypatch.setattr(tool_registry_module, "_tool_registry", registry)
    yield registry


@pytest.fixture
async def db(tmp_path, monkeypatch) -> AsyncGenerator[Database, None]:
    path = str(tmp_path / "toolacc.db")
    database = Database(path)
    await database.initialize()
    monkeypatch.setattr(db_module, "_database", database)
    yield database
    await database.close()
    monkeypatch.setattr(db_module, "_database", None)


@pytest.fixture
def access_mgr(monkeypatch) -> ToolAccessManager:
    monkeypatch.setattr(tool_access_module, "_manager", None)
    return ToolAccessManager()


@pytest.fixture
async def coolify_site(db):
    user = await db.create_user(
        email="toolacc@example.com",
        name="ToolAcc",
        provider="github",
        provider_id="gh-toolacc-1",
    )
    return await db.create_site(
        user_id=user["id"],
        plugin_type="coolify",
        alias="prod",
        url="https://coolify.example.com",
        credentials=b"x",
    )


@pytest.fixture
async def wordpress_site(db):
    user = await db.create_user(
        email="wp@example.com",
        name="wp",
        provider="github",
        provider_id="gh-wp-1",
    )
    return await db.create_site(
        user_id=user["id"],
        plugin_type="wordpress",
        alias="blog",
        url="https://blog.example.com",
        credentials=b"x",
    )


# ---------------------------------------------------------------------------
# ToolDefinition defaults
# ---------------------------------------------------------------------------


class TestToolDefinitionDefaults:
    def test_default_category_and_sensitivity(self):
        t = ToolDefinition(
            name="legacy_tool",
            description="legacy",
            handler=_noop_handler,
            plugin_type="wordpress",
        )
        assert t.category == "read"
        assert t.sensitivity == "normal"

    def test_explicit_category(self):
        t = ToolDefinition(
            name="new_tool",
            description="x",
            handler=_noop_handler,
            plugin_type="coolify",
            category="crud",
            sensitivity="sensitive",
        )
        assert t.category == "crud"
        assert t.sensitivity == "sensitive"


# ---------------------------------------------------------------------------
# Scope → category mapping
# ---------------------------------------------------------------------------


class TestScopesToCategories:
    def test_read_only(self):
        assert scopes_to_categories(["read"]) == {"read"}

    def test_write_is_superset_of_read(self):
        cats = scopes_to_categories(["write"])
        assert "read" in cats and "crud" in cats and "lifecycle" in cats
        assert "system" not in cats

    def test_admin_includes_everything(self):
        assert scopes_to_categories(["admin"]) == SCOPE_TO_CATEGORIES["admin"]

    def test_additive_scopes(self):
        cats = scopes_to_categories(["read", "deploy"])
        assert cats == {"read", "lifecycle"}

    def test_unknown_scope_ignored(self):
        assert scopes_to_categories(["bogus"]) == set()


# ---------------------------------------------------------------------------
# apply_scope_filter
# ---------------------------------------------------------------------------


class TestScopeFilter:
    def test_read_scope_drops_lifecycle_crud_system(self, access_mgr):
        out = {t.name for t in access_mgr.apply_scope_filter(_SAMPLE_TOOLS, ["read"])}
        assert "coolify_list_applications" in out
        assert "wordpress_list_posts" in out  # legacy default category
        assert "coolify_start_application" not in out
        assert "coolify_create_application_public" not in out
        assert "coolify_delete_server" not in out
        assert "coolify_get_application_logs" not in out

    def test_read_sensitive_includes_logs_and_backups(self, access_mgr):
        out = {t.name for t in access_mgr.apply_scope_filter(_SAMPLE_TOOLS, ["read:sensitive"])}
        assert "coolify_get_application_logs" in out
        assert "coolify_get_database_backups" in out
        assert "coolify_start_application" not in out
        assert "coolify_create_application_public" not in out

    def test_deploy_scope_includes_lifecycle_only(self, access_mgr):
        out = {t.name for t in access_mgr.apply_scope_filter(_SAMPLE_TOOLS, ["deploy"])}
        assert "coolify_start_application" in out
        assert "coolify_stop_application" in out
        assert "coolify_list_applications" in out
        assert "coolify_create_application_public" not in out
        assert "coolify_delete_server" not in out

    def test_write_scope_excludes_system(self, access_mgr):
        out = {t.name for t in access_mgr.apply_scope_filter(_SAMPLE_TOOLS, ["write"])}
        assert "coolify_create_application_public" in out
        assert "coolify_start_application" in out
        assert "coolify_create_application_env" in out
        assert "coolify_delete_server" not in out
        assert "coolify_get_application_logs" not in out

    def test_admin_keeps_everything(self, access_mgr):
        out = {t.name for t in access_mgr.apply_scope_filter(_SAMPLE_TOOLS, ["admin"])}
        assert out == {t.name for t in _SAMPLE_TOOLS}


# ---------------------------------------------------------------------------
# Per-site toggles
# ---------------------------------------------------------------------------


class TestSiteToggles:
    async def test_disable_hides_tool(self, db, coolify_site, access_mgr, fresh_registry):
        await access_mgr.toggle_tool(coolify_site["id"], "coolify_list_applications", enabled=False)
        tools = await access_mgr.get_visible_tools(
            site_id=coolify_site["id"], key_scopes=["admin"], plugin_type="coolify"
        )
        names = {t.name for t in tools}
        assert "coolify_list_applications" not in names
        assert "coolify_start_application" in names

    async def test_toggles_are_per_site(
        self, db, coolify_site, wordpress_site, access_mgr, fresh_registry
    ):
        # Disabling a tool on one site must not affect another site.
        await access_mgr.toggle_tool(coolify_site["id"], "coolify_list_applications", enabled=False)
        # Second coolify site inherits nothing.
        other_site = await db.create_site(
            user_id=coolify_site["user_id"],
            plugin_type="coolify",
            alias="staging",
            url="https://staging.example.com",
            credentials=b"x",
        )
        tools = await access_mgr.get_visible_tools(
            site_id=other_site["id"], key_scopes=["admin"], plugin_type="coolify"
        )
        assert "coolify_list_applications" in {t.name for t in tools}

    async def test_toggle_independent_of_scope(self, db, coolify_site, access_mgr, fresh_registry):
        await access_mgr.toggle_tool(coolify_site["id"], "coolify_list_applications", enabled=False)
        tools = await access_mgr.get_visible_tools(
            site_id=coolify_site["id"], key_scopes=["read"], plugin_type="coolify"
        )
        assert "coolify_list_applications" not in {t.name for t in tools}


# ---------------------------------------------------------------------------
# Site-level tool_scope preset
# ---------------------------------------------------------------------------


class TestSiteToolScope:
    async def test_default_admin_shows_all(self, db, coolify_site, access_mgr, fresh_registry):
        tools = await access_mgr.get_visible_tools(
            site_id=coolify_site["id"], key_scopes=["admin"], plugin_type="coolify"
        )
        assert {t.name for t in tools} == {
            t.name for t in _SAMPLE_TOOLS if t.plugin_type == "coolify"
        }

    async def test_read_preset_restricts_even_admin_key(
        self, db, coolify_site, access_mgr, fresh_registry
    ):
        """Site scope is restrictive — admin key but site=read → only read tools."""
        await db.set_site_tool_scope(coolify_site["id"], "read")
        tools = await access_mgr.get_visible_tools(
            site_id=coolify_site["id"], key_scopes=["admin"], plugin_type="coolify"
        )
        assert {t.name for t in tools} == {"coolify_list_applications"}

    async def test_key_scope_and_site_scope_intersect(
        self, db, coolify_site, access_mgr, fresh_registry
    ):
        """Key=write + site=deploy → intersection = lifecycle + read."""
        await db.set_site_tool_scope(coolify_site["id"], "deploy")
        tools = await access_mgr.get_visible_tools(
            site_id=coolify_site["id"], key_scopes=["write"], plugin_type="coolify"
        )
        names = {t.name for t in tools}
        assert "coolify_list_applications" in names  # read
        assert "coolify_start_application" in names  # lifecycle
        assert "coolify_stop_application" in names  # lifecycle
        assert "coolify_create_application_public" not in names  # crud (not in deploy)
        assert "coolify_create_application_env" not in names  # env (not in deploy)

    async def test_custom_preset_skips_site_filter(
        self, db, coolify_site, access_mgr, fresh_registry
    ):
        """tool_scope='custom' means per-tool toggles only — no category gate."""
        await db.set_site_tool_scope(coolify_site["id"], "custom")
        tools = await access_mgr.get_visible_tools(
            site_id=coolify_site["id"], key_scopes=["admin"], plugin_type="coolify"
        )
        # All coolify tools visible because no site-scope filter applied.
        assert "coolify_delete_server" in {t.name for t in tools}


# ---------------------------------------------------------------------------
# Bulk toggle (scoped to a plugin)
# ---------------------------------------------------------------------------


class TestBulkToggle:
    async def test_bulk_disable_by_scope_affects_only_plugin(
        self, db, coolify_site, access_mgr, fresh_registry
    ):
        n = await access_mgr.bulk_toggle_by_scope(
            coolify_site["id"], "deploy", enabled=False, plugin_type="coolify"
        )
        # deploy → read + lifecycle. In sample: list + 2 lifecycle = 3
        assert n == 3

        tools = await access_mgr.get_visible_tools(
            site_id=coolify_site["id"], key_scopes=["admin"], plugin_type="coolify"
        )
        names = {t.name for t in tools}
        assert "coolify_start_application" not in names
        assert "coolify_stop_application" not in names
        assert "coolify_list_applications" not in names
        assert "coolify_create_application_public" in names
        assert "coolify_delete_server" in names

    async def test_unknown_scope_raises(self, db, coolify_site, access_mgr, fresh_registry):
        with pytest.raises(ValueError):
            await access_mgr.bulk_toggle_by_scope(
                coolify_site["id"], "does_not_exist", enabled=False
            )


# ---------------------------------------------------------------------------
# list_tools_for_site end-to-end
# ---------------------------------------------------------------------------


class TestListToolsForSite:
    async def test_returns_plugin_tools_with_enabled_flag(
        self, db, coolify_site, access_mgr, fresh_registry
    ):
        tools = await access_mgr.list_tools_for_site(coolify_site["id"], "coolify")
        by_name = {t["name"]: t for t in tools}
        assert "coolify_list_applications" in by_name
        assert by_name["coolify_list_applications"]["enabled"] is True
        assert by_name["coolify_delete_server"]["category"] == "system"

    async def test_respects_toggles(self, db, coolify_site, access_mgr, fresh_registry):
        await access_mgr.toggle_tool(coolify_site["id"], "coolify_delete_server", enabled=False)
        tools = await access_mgr.list_tools_for_site(coolify_site["id"], "coolify")
        by_name = {t["name"]: t for t in tools}
        assert by_name["coolify_delete_server"]["enabled"] is False
