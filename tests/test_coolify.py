"""
Tests for Coolify MCP Plugin

Unit tests with mocked HTTP responses.
"""

import json
from unittest.mock import AsyncMock

import pytest

from plugins.coolify.client import CoolifyClient
from plugins.coolify.handlers import applications, deployments, servers
from plugins.coolify.plugin import CoolifyPlugin

# === Fixtures ===


@pytest.fixture
def client():
    """Create a CoolifyClient instance for testing."""
    return CoolifyClient(site_url="https://coolify.test.com", token="test-token-123")


@pytest.fixture
def plugin():
    """Create a CoolifyPlugin instance for testing."""
    config = {"url": "https://coolify.test.com", "token": "test-token-123"}
    return CoolifyPlugin(config, project_id="coolify_test")


# === Client Tests ===


class TestCoolifyClient:
    """Tests for CoolifyClient."""

    def test_init(self, client):
        """Test client initialization."""
        assert client.api_base == "https://coolify.test.com/api/v1"
        assert client.token == "test-token-123"

    def test_headers(self, client):
        """Test Bearer token authentication headers."""
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-token-123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_url_trailing_slash(self):
        """Test URL normalization."""
        client = CoolifyClient(site_url="https://coolify.test.com/", token="t")
        assert client.api_base == "https://coolify.test.com/api/v1"


# === Plugin Tests ===


class TestCoolifyPlugin:
    """Tests for CoolifyPlugin."""

    def test_plugin_name(self):
        """Test plugin name."""
        assert CoolifyPlugin.get_plugin_name() == "coolify"

    def test_required_config_keys(self):
        """Test required config keys."""
        assert CoolifyPlugin.get_required_config_keys() == ["url", "token"]

    def test_missing_config_raises(self):
        """Test that missing config raises ValueError."""
        with pytest.raises(ValueError, match="Missing required"):
            CoolifyPlugin({"url": "https://coolify.test.com"})

    def test_tool_specifications(self):
        """Test that tool specifications are returned."""
        specs = CoolifyPlugin.get_tool_specifications()
        assert len(specs) == 30  # 17 apps + 5 deployments + 8 servers

        # Check all specs have required fields
        for spec in specs:
            assert "name" in spec
            assert "method_name" in spec
            assert "description" in spec
            assert "schema" in spec
            assert "scope" in spec
            assert spec["scope"] in ("read", "write", "admin")

    def test_tool_names_unique(self):
        """Test that all tool names are unique."""
        specs = CoolifyPlugin.get_tool_specifications()
        names = [s["name"] for s in specs]
        assert len(names) == len(set(names))

    def test_plugin_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.client is not None
        assert plugin.client.token == "test-token-123"


# === Application Handler Tests ===


class TestApplicationHandlers:
    """Tests for application handler functions."""

    def test_app_tool_count(self):
        """Test application tool specification count."""
        specs = applications.get_tool_specifications()
        assert len(specs) == 17

    @pytest.mark.asyncio
    async def test_list_applications(self, client):
        """Test list_applications handler."""
        mock_apps = [
            {"uuid": "app-1", "name": "test-app", "status": "running"},
            {"uuid": "app-2", "name": "test-app-2", "status": "stopped"},
        ]
        client.list_applications = AsyncMock(return_value=mock_apps)

        result = await applications.list_applications(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2
        assert len(data["applications"]) == 2
        client.list_applications.assert_called_once_with(tag=None)

    @pytest.mark.asyncio
    async def test_get_application(self, client):
        """Test get_application handler."""
        mock_app = {"uuid": "app-1", "name": "mcphub", "status": "running", "fqdn": "mcp.test.com"}
        client.get_application = AsyncMock(return_value=mock_app)

        result = await applications.get_application(client, uuid="app-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["application"]["name"] == "mcphub"
        client.get_application.assert_called_once_with("app-1")

    @pytest.mark.asyncio
    async def test_start_application(self, client):
        """Test start_application handler."""
        mock_response = {"message": "Deployment request queued.", "deployment_uuid": "dep-123"}
        client.start_application = AsyncMock(return_value=mock_response)

        result = await applications.start_application(client, uuid="app-1", force=True)
        data = json.loads(result)

        assert data["success"] is True
        assert "deployment queued" in data["message"]
        client.start_application.assert_called_once_with("app-1", force=True, instant_deploy=False)

    @pytest.mark.asyncio
    async def test_stop_application(self, client):
        """Test stop_application handler."""
        mock_response = {"message": "Application stopping request queued."}
        client.stop_application = AsyncMock(return_value=mock_response)

        result = await applications.stop_application(client, uuid="app-1")
        data = json.loads(result)

        assert data["success"] is True
        client.stop_application.assert_called_once_with("app-1", docker_cleanup=True)

    @pytest.mark.asyncio
    async def test_restart_application(self, client):
        """Test restart_application handler."""
        mock_response = {"message": "Restart request queued.", "deployment_uuid": "dep-456"}
        client.restart_application = AsyncMock(return_value=mock_response)

        result = await applications.restart_application(client, uuid="app-1")
        data = json.loads(result)

        assert data["success"] is True
        client.restart_application.assert_called_once_with("app-1")

    @pytest.mark.asyncio
    async def test_get_application_logs(self, client):
        """Test get_application_logs handler."""
        mock_logs = {"logs": "2026-04-02 Starting application..."}
        client.get_application_logs = AsyncMock(return_value=mock_logs)

        result = await applications.get_application_logs(client, uuid="app-1", lines=50)
        data = json.loads(result)

        assert data["success"] is True
        client.get_application_logs.assert_called_once_with("app-1", lines=50)

    @pytest.mark.asyncio
    async def test_list_application_envs(self, client):
        """Test list_application_envs handler."""
        mock_envs = [
            {"key": "DATABASE_URL", "value": "postgres://..."},
            {"key": "SECRET_KEY", "value": "***"},
        ]
        client.list_application_envs = AsyncMock(return_value=mock_envs)

        result = await applications.list_application_envs(client, uuid="app-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_create_application_env(self, client):
        """Test create_application_env handler."""
        mock_response = {"uuid": "env-123"}
        client.create_application_env = AsyncMock(return_value=mock_response)

        result = await applications.create_application_env(
            client, uuid="app-1", key="NEW_VAR", value="test_value"
        )
        data = json.loads(result)

        assert data["success"] is True
        assert "NEW_VAR" in data["message"]

    @pytest.mark.asyncio
    async def test_delete_application_env(self, client):
        """Test delete_application_env handler."""
        client.delete_application_env = AsyncMock(return_value=None)

        result = await applications.delete_application_env(client, uuid="app-1", env_uuid="env-123")
        data = json.loads(result)

        assert data["success"] is True
        client.delete_application_env.assert_called_once_with("app-1", "env-123")

    @pytest.mark.asyncio
    async def test_create_application_public(self, client):
        """Test create_application_public handler."""
        mock_response = {"uuid": "new-app-uuid"}
        client.create_application_public = AsyncMock(return_value=mock_response)

        result = await applications.create_application_public(
            client,
            project_uuid="proj-1",
            server_uuid="srv-1",
            environment_name="production",
            git_repository="https://github.com/test/repo",
            git_branch="main",
            build_pack="nixpacks",
            ports_exposes="3000",
        )
        data = json.loads(result)

        assert data["success"] is True
        assert data["application"]["uuid"] == "new-app-uuid"

    @pytest.mark.asyncio
    async def test_update_application(self, client):
        """Test update_application handler."""
        mock_response = {"uuid": "app-1"}
        client.update_application = AsyncMock(return_value=mock_response)

        result = await applications.update_application(
            client, uuid="app-1", name="new-name", domains="app.test.com"
        )
        data = json.loads(result)

        assert data["success"] is True
        client.update_application.assert_called_once_with(
            "app-1", {"name": "new-name", "domains": "app.test.com"}
        )

    @pytest.mark.asyncio
    async def test_delete_application(self, client):
        """Test delete_application handler."""
        mock_response = {"message": "Application deleted."}
        client.delete_application = AsyncMock(return_value=mock_response)

        result = await applications.delete_application(client, uuid="app-1")
        data = json.loads(result)

        assert data["success"] is True


# === Deployment Handler Tests ===


class TestDeploymentHandlers:
    """Tests for deployment handler functions."""

    def test_deployment_tool_count(self):
        """Test deployment tool specification count."""
        specs = deployments.get_tool_specifications()
        assert len(specs) == 5

    @pytest.mark.asyncio
    async def test_list_deployments(self, client):
        """Test list_deployments handler."""
        mock_deps = [
            {"deployment_uuid": "dep-1", "status": "in_progress"},
            {"deployment_uuid": "dep-2", "status": "queued"},
        ]
        client.list_deployments = AsyncMock(return_value=mock_deps)

        result = await deployments.list_deployments(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_deploy(self, client):
        """Test deploy handler."""
        mock_response = {
            "deployments": [
                {"message": "Deploying", "resource_uuid": "app-1", "deployment_uuid": "dep-1"}
            ]
        }
        client.deploy = AsyncMock(return_value=mock_response)

        result = await deployments.deploy(client, uuid="app-1", force=True)
        data = json.loads(result)

        assert data["success"] is True
        client.deploy.assert_called_once_with(tag=None, uuid="app-1", force=True)

    @pytest.mark.asyncio
    async def test_cancel_deployment(self, client):
        """Test cancel_deployment handler."""
        mock_response = {"message": "Cancelled", "status": "cancelled-by-user"}
        client.cancel_deployment = AsyncMock(return_value=mock_response)

        result = await deployments.cancel_deployment(client, uuid="dep-1")
        data = json.loads(result)

        assert data["success"] is True
        client.cancel_deployment.assert_called_once_with("dep-1")

    @pytest.mark.asyncio
    async def test_list_app_deployments(self, client):
        """Test list_app_deployments handler."""
        mock_deps = [{"deployment_uuid": "dep-1", "status": "finished"}]
        client.list_app_deployments = AsyncMock(return_value=mock_deps)

        result = await deployments.list_app_deployments(client, uuid="app-1", skip=0, take=5)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 1
        client.list_app_deployments.assert_called_once_with("app-1", skip=0, take=5)


# === Server Handler Tests ===


class TestServerHandlers:
    """Tests for server handler functions."""

    def test_server_tool_count(self):
        """Test server tool specification count."""
        specs = servers.get_tool_specifications()
        assert len(specs) == 8

    @pytest.mark.asyncio
    async def test_list_servers(self, client):
        """Test list_servers handler."""
        mock_servers = [
            {"uuid": "srv-1", "name": "main-server", "ip": "1.2.3.4"},
        ]
        client.list_servers = AsyncMock(return_value=mock_servers)

        result = await servers.list_servers(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 1
        assert data["servers"][0]["name"] == "main-server"

    @pytest.mark.asyncio
    async def test_get_server(self, client):
        """Test get_server handler."""
        mock_server = {
            "uuid": "srv-1",
            "name": "main-server",
            "ip": "1.2.3.4",
            "settings": {"is_reachable": True},
        }
        client.get_server = AsyncMock(return_value=mock_server)

        result = await servers.get_server(client, uuid="srv-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["server"]["settings"]["is_reachable"] is True

    @pytest.mark.asyncio
    async def test_get_server_resources(self, client):
        """Test get_server_resources handler."""
        mock_resources = [
            {"uuid": "app-1", "name": "mcphub", "type": "application", "status": "running"},
            {"uuid": "db-1", "name": "postgres", "type": "database", "status": "running"},
        ]
        client.get_server_resources = AsyncMock(return_value=mock_resources)

        result = await servers.get_server_resources(client, uuid="srv-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_server_domains(self, client):
        """Test get_server_domains handler."""
        mock_domains = [{"ip": "1.2.3.4", "domains": ["mcp.test.com", "blog.test.com"]}]
        client.get_server_domains = AsyncMock(return_value=mock_domains)

        result = await servers.get_server_domains(client, uuid="srv-1")
        data = json.loads(result)

        assert data["success"] is True
        assert len(data["domains"]) == 1

    @pytest.mark.asyncio
    async def test_validate_server(self, client):
        """Test validate_server handler."""
        mock_response = {"message": "Validation started."}
        client.validate_server = AsyncMock(return_value=mock_response)

        result = await servers.validate_server(client, uuid="srv-1")
        data = json.loads(result)

        assert data["success"] is True
        assert "validation started" in data["message"].lower()


# === Health Check Tests ===


class TestHealthCheck:
    """Tests for plugin health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, plugin):
        """Test successful health check."""
        plugin.client.request = AsyncMock(return_value={"version": "4.0.0"})

        result = await plugin.health_check()
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, plugin):
        """Test failed health check."""
        plugin.client.request = AsyncMock(side_effect=Exception("Connection refused"))

        result = await plugin.health_check()
        assert result["healthy"] is False
        assert "Connection refused" in result["message"]
