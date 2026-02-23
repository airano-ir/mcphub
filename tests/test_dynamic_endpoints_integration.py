"""
Integration tests for the per-user dynamic MCP endpoints.
Uses Starlette TestClient to simulate real HTTP requests through the server.
"""
import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import json

from server import create_multi_endpoint_app

app = create_multi_endpoint_app()
client = TestClient(app)

@pytest.fixture
def mock_managers():
    """Mock the core managers to avoid needing a real database or keys."""
    
    # Mock Site Manager
    mock_site_manager = MagicMock()
    mock_site_manager.list_all_sites.return_value = []
    
    # Mock Key Manager
    mock_key_manager = AsyncMock()
    mock_key_manager.validate_key.return_value = {
        "key_id": "test-key-123",
        "user_id": "user-123",
        "scopes": "read write"
    }
    
    # Mock Database
    mock_db = AsyncMock()
    mock_db.get_site_by_alias.return_value = {
        "id": "site-123",
        "user_id": "user-123",
        "plugin_type": "wordpress",
        "alias": "myblog",
        "url": "https://example.com",
        "credentials": b"encrypted-blob",
        "status": "active"
    }
    
    with patch("server.get_site_manager", return_value=mock_site_manager), \
         patch("core.user_keys.get_user_key_manager", return_value=mock_key_manager), \
         patch("core.database.get_database", return_value=mock_db):
        yield {
            "key_manager": mock_key_manager,
            "db": mock_db
        }

@pytest.mark.integration
def test_dynamic_endpoint_unauthorized():
    """Test that requests without API key are rejected."""
    response = client.post(
        "/u/user-123/myblog/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    )
    assert response.status_code == 401
    
@pytest.mark.integration
def test_dynamic_endpoint_invalid_method(mock_managers):
    """Test that unauthorized methods or valid requests with bad structure return JSON-RPC errors."""
    response = client.post(
        "/u/user-123/myblog/mcp",
        headers={"Authorization": "Bearer mhu_test-key"},
        json={"jsonrpc": "2.0", "id": 1, "method": "invalid_method"}
    )
    assert response.status_code == 200 # JSON-RPC errors are 200 OK
    data = response.json()
    assert "error" in data
    assert "not supported" in data["error"]["message"].lower()

@pytest.mark.integration
def test_dynamic_endpoint_initialize(mock_managers):
    """Test standard MCP initialize on the dynamic endpoint."""
    response = client.post(
        "/u/user-123/myblog/mcp",
        headers={"Authorization": "Bearer mhu_test-key"},
        json={
            "jsonrpc": "2.0", 
            "id": 1, 
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "capabilities" in data["result"]
    assert "serverInfo" in data["result"]

@pytest.mark.integration
def test_dynamic_endpoint_mismatched_user(mock_managers):
    """Test that if the key belongs to a different user, it's rejected."""
    mock_managers["key_manager"].validate_key.return_value = {
        "key_id": "test-key-123",
        "user_id": "different-user-456",
        "scopes": "read write"
    }
    
    response = client.post(
        "/u/user-123/myblog/mcp",
        headers={"Authorization": "Bearer mhu_test-key"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    )
    assert response.status_code == 403
    data = response.json()
    assert "does not match" in data["error"]["message"]
