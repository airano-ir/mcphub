"""
Tests for Coolify Databases Handler

Unit tests with mocked HTTP responses.
"""

import json
from unittest.mock import AsyncMock

import pytest

from plugins.coolify.client import CoolifyClient
from plugins.coolify.handlers import databases


@pytest.fixture
def client():
    """Create a CoolifyClient instance for testing."""
    return CoolifyClient(site_url="https://coolify.test.com", token="test-token-123")


class TestDatabaseToolSpecs:
    """Tests for database tool specifications."""

    def test_database_tool_count(self):
        """Test database tool specification count."""
        specs = databases.get_tool_specifications()
        assert len(specs) == 16

    def test_tool_specs_have_required_fields(self):
        """Test all specs have required fields."""
        for spec in databases.get_tool_specifications():
            assert "name" in spec
            assert "method_name" in spec
            assert "description" in spec
            assert "schema" in spec
            assert "scope" in spec
            assert spec["scope"] in ("read", "write", "admin")

    def test_tool_names_unique(self):
        """Test that all tool names are unique."""
        specs = databases.get_tool_specifications()
        names = [s["name"] for s in specs]
        assert len(names) == len(set(names))

    def test_all_db_types_present(self):
        """Test all 6 database creation tools exist."""
        specs = databases.get_tool_specifications()
        names = [s["name"] for s in specs]
        for db_type in ["postgresql", "mysql", "mariadb", "mongodb", "redis", "clickhouse"]:
            assert f"create_{db_type}" in names

    def test_scope_distribution(self):
        """Test correct scope assignments."""
        specs = databases.get_tool_specifications()
        by_scope = {}
        for s in specs:
            by_scope.setdefault(s["scope"], []).append(s["name"])
        assert "list_databases" in by_scope["read"]
        assert "delete_database" in by_scope["admin"]
        assert "start_database" in by_scope["write"]


class TestDatabaseHandlers:
    """Tests for database handler functions."""

    @pytest.mark.asyncio
    async def test_list_databases(self, client):
        """Test list_databases handler."""
        mock_dbs = [
            {"uuid": "db-1", "name": "postgres-main", "type": "postgresql", "status": "running"},
            {"uuid": "db-2", "name": "redis-cache", "type": "redis", "status": "running"},
        ]
        client.list_databases = AsyncMock(return_value=mock_dbs)

        result = await databases.list_databases(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2
        client.list_databases.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_database(self, client):
        """Test get_database handler."""
        mock_db = {"uuid": "db-1", "name": "postgres-main", "type": "postgresql"}
        client.get_database = AsyncMock(return_value=mock_db)

        result = await databases.get_database(client, uuid="db-1")
        data = json.loads(result)

        assert data["success"] is True
        assert data["database"]["name"] == "postgres-main"
        client.get_database.assert_called_once_with("db-1")

    @pytest.mark.asyncio
    async def test_update_database(self, client):
        """Test update_database handler."""
        mock_response = {"uuid": "db-1"}
        client.update_database = AsyncMock(return_value=mock_response)

        result = await databases.update_database(client, uuid="db-1", name="renamed-db")
        data = json.loads(result)

        assert data["success"] is True
        assert "updated" in data["message"].lower()
        client.update_database.assert_called_once_with("db-1", {"name": "renamed-db"})

    @pytest.mark.asyncio
    async def test_delete_database(self, client):
        """Test delete_database handler."""
        mock_response = {"message": "Database deleted."}
        client.delete_database = AsyncMock(return_value=mock_response)

        result = await databases.delete_database(client, uuid="db-1")
        data = json.loads(result)

        assert data["success"] is True
        assert "deleted" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_start_database(self, client):
        """Test start_database handler."""
        mock_response = {"message": "Starting."}
        client.start_database = AsyncMock(return_value=mock_response)

        result = await databases.start_database(client, uuid="db-1")
        data = json.loads(result)

        assert data["success"] is True
        client.start_database.assert_called_once_with("db-1")

    @pytest.mark.asyncio
    async def test_stop_database(self, client):
        """Test stop_database handler."""
        mock_response = {"message": "Stopping."}
        client.stop_database = AsyncMock(return_value=mock_response)

        result = await databases.stop_database(client, uuid="db-1")
        data = json.loads(result)

        assert data["success"] is True
        client.stop_database.assert_called_once_with("db-1")

    @pytest.mark.asyncio
    async def test_restart_database(self, client):
        """Test restart_database handler."""
        mock_response = {"message": "Restarting."}
        client.restart_database = AsyncMock(return_value=mock_response)

        result = await databases.restart_database(client, uuid="db-1")
        data = json.loads(result)

        assert data["success"] is True
        client.restart_database.assert_called_once_with("db-1")

    @pytest.mark.asyncio
    async def test_create_postgresql(self, client):
        """Test create_postgresql handler."""
        mock_response = {"uuid": "db-new", "type": "postgresql"}
        client.create_database = AsyncMock(return_value=mock_response)

        result = await databases.create_postgresql(
            client,
            project_uuid="proj-1",
            server_uuid="srv-1",
            environment_name="production",
        )
        data = json.loads(result)

        assert data["success"] is True
        assert "postgresql" in data["message"].lower()
        client.create_database.assert_called_once_with(
            "postgresql",
            {
                "project_uuid": "proj-1",
                "server_uuid": "srv-1",
                "environment_name": "production",
            },
        )

    @pytest.mark.asyncio
    async def test_create_redis(self, client):
        """Test create_redis handler."""
        mock_response = {"uuid": "db-new", "type": "redis"}
        client.create_database = AsyncMock(return_value=mock_response)

        result = await databases.create_redis(
            client,
            project_uuid="proj-1",
            server_uuid="srv-1",
            environment_name="production",
            name="my-cache",
        )
        data = json.loads(result)

        assert data["success"] is True
        assert "redis" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_database_backups(self, client):
        """Test get_database_backups handler."""
        mock_backups = {"enabled": True, "frequency": "0 0 * * *", "backups": []}
        client.get_database_backups = AsyncMock(return_value=mock_backups)

        result = await databases.get_database_backups(client, uuid="db-1")
        data = json.loads(result)

        assert data["success"] is True
        client.get_database_backups.assert_called_once_with("db-1")

    @pytest.mark.asyncio
    async def test_create_database_backup(self, client):
        """Test create_database_backup handler."""
        mock_response = {"message": "Backup started."}
        client.create_database_backup = AsyncMock(return_value=mock_response)

        result = await databases.create_database_backup(client, uuid="db-1")
        data = json.loads(result)

        assert data["success"] is True
        assert "backup" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_list_backup_executions(self, client):
        """Test list_backup_executions handler."""
        mock_executions = [
            {"id": 1, "database_uuid": "db-1", "status": "success"},
            {"id": 2, "database_uuid": "db-1", "status": "failed"},
        ]
        client.list_backup_executions = AsyncMock(return_value=mock_executions)

        result = await databases.list_backup_executions(client)
        data = json.loads(result)

        assert data["success"] is True
        assert data["count"] == 2
