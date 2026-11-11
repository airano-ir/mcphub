"""
Tests for Coolify Services Handler

Unit tests with mocked HTTP responses.
"""

import json
from unittest.mock import AsyncMock

import pytest

from plugins.coolify.client import CoolifyClient
from plugins.coolify.handlers import services


@pytest.fixture
def client():
    """Create a CoolifyClient instance for testing."""
    return CoolifyClient(site_url="https://coolify.test.com", token="test-token-123")


class TestServiceToolSpecs:
    """Tests for service tool specifications."""

    def test_service_tool_count(self):
        """Test service tool specification count."""
        specs = services.get_tool_specifications()
        assert len(specs) == 13

    def test_tool_specs_have_required_fields(self):
        """Test all specs have required fields."""
        for spec in services.get_tool_specifications():
            assert "name" in spec
            assert "method_name" in spec
            assert "description" in spec
            assert "schema" in spec
            assert "scope" in spec
            assert spec["scope"] in ("read", "write", "admin")

    def test_tool_names_unique(self):
        """Test that all tool names are unique."""
        specs = services.get_tool_specifications()
        names = [s["name"] for s in specs]
        assert len(names) == len(set(names))

    def test_scope_distribution(self):
        """Test correct scope assignments."""
        specs = services.get_tool_specifications()
        by_scope = {}
        for s in specs:
            by_scope.setdefault(s["scope"], []).append(s["name"])
        assert "list_services" in by_scope["read"]
        assert "list_service_envs" in by_scope["read"]
        assert "delete_service" in by_scope["admin"]
        assert "start_service" in by_scope["write"]
        assert "create_service_env" in by_scope["write"]


class TestServiceHandlers:
    """Tests for service handler functions."""

    @pytest.mark.asyncio
    async def test_list_services(self, client):
        """Test list_services handler."""
        mock_services = [
            {"uuid": "svc-1", "name": "plausible", "status": "running"},
            {"uuid": "svc-2", "name": "minio", "status": "stopped"},
        ]
        client.list_services = AsyncMock(return_value=mock_services)

        result = await services.list_services(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2
        client.list_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_services_filters_and_compacts(self, client):
        """list_services should trim large Coolify payloads by default."""
        mock_services = [
            {
                "uuid": "svc-1",
                "name": "plausible",
                "status": "running",
                "docker_compose_raw": "x" * 1000,
            },
            {"uuid": "svc-2", "name": "minio", "status": "stopped"},
        ]
        client.list_services = AsyncMock(return_value=mock_services)

        result = await services.list_services(client, name="plausible", fields=["uuid", "name"])
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 1
        assert data["total"] == 1
        assert data["services"] == [{"uuid": "svc-1", "name": "plausible"}]

    @pytest.mark.asyncio
    async def test_get_service(self, client):
        """Test get_service handler."""
        mock_service = {"uuid": "svc-1", "name": "plausible", "status": "running"}
        client.get_service = AsyncMock(return_value=mock_service)

        result = await services.get_service(client, uuid="svc-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["service"]["name"] == "plausible"
        client.get_service.assert_called_once_with("svc-1")

    @pytest.mark.asyncio
    async def test_create_service(self, client):
        """Test create_service handler."""
        mock_response = {"uuid": "svc-new"}
        client.create_service = AsyncMock(return_value=mock_response)

        result = await services.create_service(
            client,
            project_uuid="proj-1",
            server_uuid="srv-1",
            environment_name="production",
            type="plausible-analytics",
            name="my-plausible",
        )
        data = json.loads(result)

        assert data["success"] is True
        assert "created" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_update_service(self, client):
        """Test update_service handler."""
        mock_response = {"uuid": "svc-1"}
        client.update_service = AsyncMock(return_value=mock_response)

        result = await services.update_service(client, uuid="svc-1", name="renamed")
        data = json.loads(result)

        assert data["success"] is True
        assert "updated" in data["message"].lower()
        client.update_service.assert_called_once_with("svc-1", {"name": "renamed"})

    @pytest.mark.asyncio
    async def test_delete_service(self, client):
        """Test delete_service handler."""
        mock_response = {"message": "Service deleted."}
        client.delete_service = AsyncMock(return_value=mock_response)

        result = await services.delete_service(client, uuid="svc-1")
        data = json.loads(result)

        assert data["success"] is True
        assert "deleted" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_start_service(self, client):
        """Test start_service handler."""
        mock_response = {"message": "Starting."}
        client.start_service = AsyncMock(return_value=mock_response)

        result = await services.start_service(client, uuid="svc-1")
        data = json.loads(result)

        assert data["success"] is True
        client.start_service.assert_called_once_with("svc-1")

    @pytest.mark.asyncio
    async def test_stop_service(self, client):
        """Test stop_service handler."""
        mock_response = {"message": "Stopping."}
        client.stop_service = AsyncMock(return_value=mock_response)

        result = await services.stop_service(client, uuid="svc-1")
        data = json.loads(result)

        assert data["success"] is True
        client.stop_service.assert_called_once_with("svc-1")

    @pytest.mark.asyncio
    async def test_restart_service(self, client):
        """Test restart_service handler."""
        mock_response = {"message": "Restarting."}
        client.restart_service = AsyncMock(return_value=mock_response)

        result = await services.restart_service(client, uuid="svc-1")
        data = json.loads(result)

        assert data["success"] is True
        client.restart_service.assert_called_once_with("svc-1")


class TestServiceEnvHandlers:
    """Tests for service environment variable handlers."""

    @pytest.mark.asyncio
    async def test_list_service_envs(self, client):
        """Test list_service_envs handler."""
        mock_envs = [
            {"key": "DATABASE_URL", "value": "postgres://..."},
            {"key": "SECRET", "value": "***"},
        ]
        client.list_service_envs = AsyncMock(return_value=mock_envs)

        result = await services.list_service_envs(client, uuid="svc-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_create_service_env(self, client):
        """Test create_service_env handler."""
        mock_response = {"uuid": "env-123"}
        client.get_service = AsyncMock(return_value={"uuid": "svc-1"})
        client.create_service_env = AsyncMock(return_value=mock_response)

        result = await services.create_service_env(
            client, uuid="svc-1", key="NEW_VAR", value="test"
        )
        data = json.loads(result)

        assert data["success"] is True
        assert "NEW_VAR" in data["message"]
        client.get_service.assert_called_once_with("svc-1")

    @pytest.mark.asyncio
    async def test_update_service_env(self, client):
        """Test update_service_env handler."""
        mock_response = {"uuid": "env-123"}
        client.get_service = AsyncMock(return_value={"uuid": "svc-1"})
        client.update_service_env = AsyncMock(return_value=mock_response)

        result = await services.update_service_env(
            client, uuid="svc-1", key="EXISTING_VAR", value="new_val"
        )
        data = json.loads(result)

        assert data["success"] is True
        assert "EXISTING_VAR" in data["message"]
        client.get_service.assert_called_once_with("svc-1")

    @pytest.mark.asyncio
    async def test_update_service_env_blocks_compose_environment_collision(self, client):
        """Service env writes should fail when compose hardcodes the same key."""
        client.get_service = AsyncMock(
            return_value={
                "uuid": "svc-1",
                "docker_compose_raw": """
services:
  app:
    image: example/app
    environment:
      EXISTING_VAR: hardcoded
      - OTHER_VAR=value
""",
            }
        )
        client.update_service_env = AsyncMock(return_value={"uuid": "env-123"})

        with pytest.raises(ValueError, match="docker_compose_raw already hardcodes"):
            await services.update_service_env(
                client, uuid="svc-1", key="EXISTING_VAR", value="new_val"
            )

        client.update_service_env.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_service_env_can_bypass_compose_collision_guard(self, client):
        """The explicit bypass should preserve existing advanced workflows."""
        client.get_service = AsyncMock(return_value={"uuid": "svc-1"})
        client.update_service_env = AsyncMock(return_value={"uuid": "env-123"})

        result = await services.update_service_env(
            client,
            uuid="svc-1",
            key="EXISTING_VAR",
            value="new_val",
            allow_compose_environment_override=True,
        )
        data = json.loads(result)

        assert data["success"] is True
        client.get_service.assert_not_called()
        client.update_service_env.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_service_envs_bulk(self, client):
        """Test update_service_envs_bulk handler."""
        mock_response = {"message": "Updated."}
        client.get_service = AsyncMock(return_value={"uuid": "svc-1"})
        client.update_service_envs_bulk = AsyncMock(return_value=mock_response)

        env_data = [{"key": "A", "value": "1"}, {"key": "B", "value": "2"}]
        result = await services.update_service_envs_bulk(client, uuid="svc-1", data=env_data)
        data = json.loads(result)

        assert data["success"] is True
        assert "2" in data["message"]

    @pytest.mark.asyncio
    async def test_delete_service_env(self, client):
        """Test delete_service_env handler."""
        client.delete_service_env = AsyncMock(return_value=None)

        result = await services.delete_service_env(client, uuid="svc-1", env_uuid="env-123")
        data = json.loads(result)

        assert data["success"] is True
        client.delete_service_env.assert_called_once_with("svc-1", "env-123")
