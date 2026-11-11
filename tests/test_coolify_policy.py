"""Tests for optional Coolify site-level access policies."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest

import core.database as db_module
import core.tool_access as tool_access_module
import core.tool_registry as tool_registry_module
from core.coolify_policy import (
    allowed_project_uuids,
    filter_coolify_result_by_policy,
    filter_coolify_tools_by_policy,
    is_coolify_read_only,
    is_coolify_tool_allowed,
)
from core.database import Database
from core.site_api import get_credential_fields, validate_credentials
from core.tool_registry import ToolDefinition, ToolRegistry
from core.user_endpoints import _get_visible_tools_for_site


class FakeCoolifyEnvironmentClient:
    def __init__(self, environments_by_project: dict[str, list[dict[str, Any]]]):
        self.environments_by_project = environments_by_project
        self.calls: list[str] = []

    async def list_environments(self, project_uuid: str) -> list[dict[str, Any]]:
        self.calls.append(project_uuid)
        return self.environments_by_project[project_uuid]


async def _noop_handler(**_kwargs):
    return "ok"


def _tool(
    name: str,
    *,
    scope: str = "read",
    category: str = "read",
    plugin_type: str = "coolify",
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"desc {name}",
        input_schema={"type": "object", "properties": {}},
        handler=_noop_handler,
        required_scope=scope,
        plugin_type=plugin_type,
        category=category,
    )


@pytest.fixture
def fake_coolify_client() -> FakeCoolifyEnvironmentClient:
    return FakeCoolifyEnvironmentClient(
        {
            "proj-1": [
                {"id": 5, "uuid": "env-prod", "name": "production"},
                {"id": "6", "uuid": "env-stage", "name": "staging"},
            ],
            "proj-2": [
                {"id": 9, "uuid": "env-other", "name": "production"},
            ],
        }
    )


@pytest.fixture
def sample_tools() -> list[ToolDefinition]:
    return [
        _tool("coolify_list_applications"),
        _tool("coolify_get_application", category="read"),
        _tool("coolify_list_services"),
        _tool("coolify_get_service", category="read"),
        _tool("coolify_list_databases"),
        _tool("coolify_get_database", category="read_sensitive"),
        _tool("coolify_get_project"),
        _tool("coolify_list_environments"),
        _tool("coolify_get_server_resources"),
        _tool("coolify_create_application_public", scope="write", category="crud"),
        _tool("coolify_start_application", scope="write", category="lifecycle"),
        _tool("coolify_delete_server", scope="admin", category="system"),
        _tool("wordpress_list_posts", plugin_type="wordpress"),
    ]


@pytest.fixture
def fresh_registry(
    monkeypatch, sample_tools: list[ToolDefinition]
) -> Generator[ToolRegistry, None, None]:
    registry = ToolRegistry()
    for tool in sample_tools:
        registry.register(tool)
    monkeypatch.setattr(tool_registry_module, "_tool_registry", registry)
    monkeypatch.setattr(tool_access_module, "_manager", None)
    yield registry


@pytest.fixture
async def db(tmp_path, monkeypatch) -> AsyncGenerator[Database, None]:
    database = Database(str(tmp_path / "coolify-policy.db"))
    await database.initialize()
    monkeypatch.setattr(db_module, "_database", database)
    yield database
    await database.close()
    monkeypatch.setattr(db_module, "_database", None)


@pytest.fixture
async def coolify_site(db: Database):
    user = await db.create_user(
        email="coolify-policy@example.com",
        name="Coolify Policy",
        provider="github",
        provider_id="gh-coolify-policy",
    )
    return await db.create_site(
        user_id=user["id"],
        plugin_type="coolify",
        alias="prod",
        url="https://coolify.example.com",
        credentials=b"x",
    )


class TestCoolifyDashboardCredentialFields:
    def test_coolify_ui_exposes_optional_policy_credentials(self):
        fields = {field["name"]: field for field in get_credential_fields("coolify")}
        assert fields["token"]["required"] is True
        assert fields["read_only"]["type"] == "checkbox"
        assert fields["read_only"]["required"] is False
        assert fields["project_uuid"]["type"] == "text"
        assert fields["project_uuid"]["required"] is False
        assert fields["allowed_project_uuids"]["type"] == "text"
        assert fields["allowed_project_uuids"]["required"] is False

    def test_coolify_optional_policy_credentials_validate_from_dashboard_values(self):
        valid, errors = validate_credentials(
            "coolify",
            {
                "token": "tk",
                "read_only": True,
                "project_uuid": "proj-1",
                "allowed_project_uuids": "proj-1,proj-2",
            },
        )
        assert valid is True
        assert errors == []


class TestCoolifyPolicyParsing:
    def test_read_only_truthy_values(self):
        assert is_coolify_read_only({"read_only": True}) is True
        assert is_coolify_read_only({"coolify_read_only": "yes"}) is True
        assert is_coolify_read_only({"read_only": "false"}) is False

    def test_project_uuid_aliases(self):
        assert allowed_project_uuids({"project_uuid": "p1"}) == {"p1"}
        assert allowed_project_uuids({"coolify_project_uuid": "p2"}) == {"p2"}
        assert allowed_project_uuids({"allowed_project_uuids": "p1, p2\n p3"}) == {
            "p1",
            "p2",
            "p3",
        }
        assert allowed_project_uuids({"coolify_allowed_project_uuids": ["p4", "p5"]}) == {
            "p4",
            "p5",
        }


class TestCoolifyPolicyToolAuthorization:
    def test_no_policy_preserves_existing_behaviour(self, sample_tools):
        allowed = {t.name for t in filter_coolify_tools_by_policy(sample_tools, {})}
        assert "coolify_list_applications" in allowed
        assert "coolify_create_application_public" in allowed
        assert "wordpress_list_posts" in allowed

    def test_read_only_hides_mutating_coolify_tools_but_keeps_read_and_other_plugins(
        self, sample_tools
    ):
        allowed = {
            t.name for t in filter_coolify_tools_by_policy(sample_tools, {"read_only": True})
        }
        assert "coolify_list_applications" in allowed
        assert "coolify_get_application" in allowed
        assert "coolify_create_application_public" not in allowed
        assert "coolify_start_application" not in allowed
        assert "coolify_delete_server" not in allowed
        assert "wordpress_list_posts" in allowed

    def test_project_policy_keeps_project_argument_and_project_filtered_read_tools(
        self, sample_tools
    ):
        allowed = {
            t.name
            for t in filter_coolify_tools_by_policy(
                sample_tools, {"coolify_project_uuid": "proj-1"}
            )
        }
        assert "coolify_get_project" in allowed
        assert "coolify_list_environments" in allowed
        assert "coolify_create_application_public" in allowed
        assert "coolify_list_applications" in allowed
        assert "coolify_get_application" in allowed
        assert "coolify_list_services" in allowed
        assert "coolify_get_service" in allowed
        assert "coolify_list_databases" in allowed
        assert "coolify_get_database" in allowed
        assert "coolify_get_server_resources" not in allowed

    def test_project_policy_allows_only_configured_project_uuid(self, sample_tools):
        create_tool = next(t for t in sample_tools if t.name == "coolify_create_application_public")
        ok, reason = is_coolify_tool_allowed(
            create_tool,
            {"project_uuid": "proj-1"},
            {"allowed_project_uuids": "proj-1,proj-2"},
        )
        assert ok is True
        assert reason is None

        ok, reason = is_coolify_tool_allowed(
            create_tool,
            {"project_uuid": "other"},
            {"allowed_project_uuids": "proj-1,proj-2"},
        )
        assert ok is False
        assert "not allowed" in (reason or "")

    def test_project_policy_allows_project_filtered_read_tools_for_result_filtering(
        self, sample_tools
    ):
        get_app = next(t for t in sample_tools if t.name == "coolify_get_application")
        ok, reason = is_coolify_tool_allowed(
            get_app,
            {"uuid": "app-uuid"},
            {"project_uuid": "proj-1"},
        )
        assert ok is True
        assert reason is None

    async def test_project_policy_filters_list_results_by_real_environment_id_shape(
        self, fake_coolify_client
    ):
        payload = json.dumps(
            {
                "success": True,
                "count": 3,
                "total": 3,
                "truncated": False,
                "applications": [
                    {"uuid": "a1", "environment_id": 5},
                    {"uuid": "a2", "environment_id": 9},
                    {"uuid": "a3", "environment_id": "6"},
                ],
            }
        )
        filtered = json.loads(
            await filter_coolify_result_by_policy(
                "coolify_list_applications",
                payload,
                {"project_uuid": "proj-1"},
                fake_coolify_client,
                {},
            )
        )
        assert filtered["count"] == 2
        assert filtered["total"] == 2
        assert filtered["truncated"] is False
        assert filtered["policy_filtered"] is True
        assert [item["uuid"] for item in filtered["applications"]] == ["a1", "a3"]
        assert fake_coolify_client.calls == ["proj-1"]

    async def test_project_policy_filters_detail_results_outside_allowed_environment(
        self, fake_coolify_client
    ):
        payload = json.dumps(
            {
                "success": True,
                "service": {"uuid": "svc-1", "environment_id": 9},
            }
        )
        filtered = json.loads(
            await filter_coolify_result_by_policy(
                "coolify_get_service",
                payload,
                {"project_uuid": "proj-1"},
                fake_coolify_client,
                {},
            )
        )
        assert filtered["success"] is False
        assert filtered["policy_filtered"] is True
        assert "outside" in filtered["error"]

    async def test_project_policy_keeps_detail_results_inside_allowed_environment(
        self, fake_coolify_client
    ):
        payload = json.dumps(
            {
                "success": True,
                "database": {"uuid": "db-1", "environment_id": 5},
            }
        )
        filtered = json.loads(
            await filter_coolify_result_by_policy(
                "coolify_get_database",
                payload,
                {"project_uuid": "proj-1"},
                fake_coolify_client,
                {},
            )
        )
        assert filtered["success"] is True
        assert filtered["database"]["uuid"] == "db-1"

    async def test_project_environment_lookup_cache_is_reused(self, fake_coolify_client):
        cache: dict[str, Any] = {}
        for tool_name, collection_key in [
            ("coolify_list_applications", "applications"),
            ("coolify_list_services", "services"),
        ]:
            payload = json.dumps(
                {
                    "success": True,
                    "count": 1,
                    "total": 1,
                    "truncated": False,
                    collection_key: [{"uuid": "same-project", "environment_id": 5}],
                }
            )
            await filter_coolify_result_by_policy(
                tool_name,
                payload,
                {"project_uuid": "proj-1"},
                fake_coolify_client,
                cache,
            )
        assert fake_coolify_client.calls == ["proj-1"]


class TestVisibleToolsIntegration:
    async def test_tools_list_applies_coolify_read_only_policy(
        self, db, coolify_site, fresh_registry
    ):
        tools = await _get_visible_tools_for_site(
            coolify_site["id"],
            ["admin"],
            "coolify",
            {"read_only": True},
        )
        names = {t["name"] for t in tools}
        assert "coolify_list_applications" in names
        assert "coolify_create_application_public" not in names
        assert "coolify_delete_server" not in names

    async def test_tools_list_applies_project_policy_after_scope_filters(
        self, db, coolify_site, fresh_registry
    ):
        await db.set_site_tool_scope(coolify_site["id"], "admin")
        tools = await _get_visible_tools_for_site(
            coolify_site["id"],
            ["admin"],
            "coolify",
            {"project_uuid": "proj-1"},
        )
        names = {t["name"] for t in tools}
        assert "coolify_get_project" in names
        assert "coolify_list_environments" in names
        assert "coolify_list_applications" in names
        assert "coolify_get_application" in names
        assert "coolify_get_server_resources" not in names
