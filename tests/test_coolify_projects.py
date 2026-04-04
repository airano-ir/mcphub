"""
Tests for Coolify Projects & Environments Handler

Unit tests with mocked HTTP responses.
"""

import json
from unittest.mock import AsyncMock

import pytest

from plugins.coolify.client import CoolifyClient
from plugins.coolify.handlers import projects


@pytest.fixture
def client():
    """Create a CoolifyClient instance for testing."""
    return CoolifyClient(site_url="https://coolify.test.com", token="test-token-123")


class TestProjectToolSpecs:
    """Tests for project tool specifications."""

    def test_project_tool_count(self):
        """Test project tool specification count."""
        specs = projects.get_tool_specifications()
        assert len(specs) == 8

    def test_tool_specs_have_required_fields(self):
        """Test all specs have required fields."""
        for spec in projects.get_tool_specifications():
            assert "name" in spec
            assert "method_name" in spec
            assert "description" in spec
            assert "schema" in spec
            assert "scope" in spec
            assert spec["scope"] in ("read", "write", "admin")

    def test_tool_names_unique(self):
        """Test that all tool names are unique."""
        specs = projects.get_tool_specifications()
        names = [s["name"] for s in specs]
        assert len(names) == len(set(names))

    def test_scope_distribution(self):
        """Test correct scope assignments."""
        specs = projects.get_tool_specifications()
        by_scope = {}
        for s in specs:
            by_scope.setdefault(s["scope"], []).append(s["name"])
        assert "list_projects" in by_scope["read"]
        assert "get_project" in by_scope["read"]
        assert "create_project" in by_scope["write"]
        assert "delete_project" in by_scope["admin"]


class TestProjectHandlers:
    """Tests for project handler functions."""

    @pytest.mark.asyncio
    async def test_list_projects(self, client):
        """Test list_projects handler."""
        mock_projects = [
            {"uuid": "proj-1", "name": "mcphub", "description": "MCP Hub project"},
            {"uuid": "proj-2", "name": "blog", "description": "Blog project"},
        ]
        client.list_projects = AsyncMock(return_value=mock_projects)

        result = await projects.list_projects(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2
        assert len(data["projects"]) == 2
        client.list_projects.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_project(self, client):
        """Test get_project handler."""
        mock_project = {
            "uuid": "proj-1",
            "name": "mcphub",
            "description": "MCP Hub project",
            "environments": [{"name": "production"}],
        }
        client.get_project = AsyncMock(return_value=mock_project)

        result = await projects.get_project(client, uuid="proj-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["project"]["name"] == "mcphub"
        client.get_project.assert_called_once_with("proj-1")

    @pytest.mark.asyncio
    async def test_create_project(self, client):
        """Test create_project handler."""
        mock_response = {"uuid": "proj-new", "name": "new-project"}
        client.create_project = AsyncMock(return_value=mock_response)

        result = await projects.create_project(
            client, name="new-project", description="A test project"
        )
        data = json.loads(result)

        assert data["success"] is True
        assert "created" in data["message"].lower()
        client.create_project.assert_called_once_with(
            {"name": "new-project", "description": "A test project"}
        )

    @pytest.mark.asyncio
    async def test_create_project_no_description(self, client):
        """Test create_project without description."""
        mock_response = {"uuid": "proj-new"}
        client.create_project = AsyncMock(return_value=mock_response)

        result = await projects.create_project(client, name="minimal")
        data = json.loads(result)

        assert data["success"] is True
        client.create_project.assert_called_once_with({"name": "minimal"})

    @pytest.mark.asyncio
    async def test_update_project(self, client):
        """Test update_project handler."""
        mock_response = {"uuid": "proj-1"}
        client.update_project = AsyncMock(return_value=mock_response)

        result = await projects.update_project(client, uuid="proj-1", name="renamed")
        data = json.loads(result)

        assert data["success"] is True
        assert "updated" in data["message"].lower()
        client.update_project.assert_called_once_with("proj-1", {"name": "renamed"})

    @pytest.mark.asyncio
    async def test_delete_project(self, client):
        """Test delete_project handler."""
        mock_response = {"message": "Project deleted."}
        client.delete_project = AsyncMock(return_value=mock_response)

        result = await projects.delete_project(client, uuid="proj-1")
        data = json.loads(result)

        assert data["success"] is True
        assert "deleted" in data["message"].lower()
        client.delete_project.assert_called_once_with("proj-1")


class TestEnvironmentHandlers:
    """Tests for environment handler functions."""

    @pytest.mark.asyncio
    async def test_list_environments(self, client):
        """Test list_environments handler."""
        mock_envs = [
            {"name": "production", "id": 1},
            {"name": "staging", "id": 2},
        ]
        client.list_environments = AsyncMock(return_value=mock_envs)

        result = await projects.list_environments(client, project_uuid="proj-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2
        assert len(data["environments"]) == 2
        client.list_environments.assert_called_once_with("proj-1")

    @pytest.mark.asyncio
    async def test_get_environment(self, client):
        """Test get_environment handler."""
        mock_env = {"name": "production", "id": 1, "project_id": 5}
        client.get_environment = AsyncMock(return_value=mock_env)

        result = await projects.get_environment(
            client, project_uuid="proj-1", environment_name="production"
        )
        data = json.loads(result)

        assert data["success"] is True
        assert data["environment"]["name"] == "production"
        client.get_environment.assert_called_once_with("proj-1", "production")

    @pytest.mark.asyncio
    async def test_create_environment(self, client):
        """Test create_environment handler."""
        mock_response = {"name": "staging", "id": 3}
        client.create_environment = AsyncMock(return_value=mock_response)

        result = await projects.create_environment(
            client, project_uuid="proj-1", name="staging", description="Staging env"
        )
        data = json.loads(result)

        assert data["success"] is True
        assert "staging" in data["message"]
        client.create_environment.assert_called_once_with(
            "proj-1", {"name": "staging", "description": "Staging env"}
        )

    @pytest.mark.asyncio
    async def test_create_environment_no_description(self, client):
        """Test create_environment without description."""
        mock_response = {"name": "test"}
        client.create_environment = AsyncMock(return_value=mock_response)

        result = await projects.create_environment(client, project_uuid="proj-1", name="test")
        data = json.loads(result)

        assert data["success"] is True
        client.create_environment.assert_called_once_with("proj-1", {"name": "test"})
