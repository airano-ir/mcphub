import tempfile

import pytest

from core.oauth.client_registry import ClientRegistry


@pytest.fixture
def registry():
    """Create temporary client registry for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ClientRegistry(tmpdir)


def test_create_client(registry):
    """Test client creation"""
    client_id, client_secret = registry.create_client(
        client_name="Test App", redirect_uris=["http://localhost:3000/callback"]
    )

    # Check client_id format
    assert client_id.startswith("cmp_client_")

    # Check secret is generated
    assert len(client_secret) > 20

    # Retrieve client
    client = registry.get_client(client_id)
    assert client is not None
    assert client.client_name == "Test App"
    assert "authorization_code" in client.grant_types


def test_validate_client_secret(registry):
    """Test client secret validation"""
    client_id, client_secret = registry.create_client(
        client_name="Test App", redirect_uris=["http://localhost:3000/callback"]
    )

    # Valid secret
    assert registry.validate_client_secret(client_id, client_secret)

    # Invalid secret
    assert not registry.validate_client_secret(client_id, "wrong_secret")

    # Non-existent client
    assert not registry.validate_client_secret("fake_id", client_secret)


def test_list_clients(registry):
    """Test listing clients"""
    # Create multiple clients
    registry.create_client("App 1", ["http://localhost:3001/callback"])
    registry.create_client("App 2", ["http://localhost:3002/callback"])

    clients = registry.list_clients()
    assert len(clients) == 2
    assert clients[0].client_name in ["App 1", "App 2"]


def test_delete_client(registry):
    """Test client deletion"""
    client_id, _ = registry.create_client(
        client_name="Test App", redirect_uris=["http://localhost:3000/callback"]
    )

    # Delete
    assert registry.delete_client(client_id)

    # Should not exist
    assert registry.get_client(client_id) is None

    # Delete non-existent
    assert not registry.delete_client("fake_id")
