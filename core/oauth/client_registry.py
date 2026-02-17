"""
OAuth 2.1 Client Registry
Manages OAuth client registration and validation
"""

import hashlib
import json
import logging
import secrets
from pathlib import Path

from .schemas import OAuthClient

logger = logging.getLogger(__name__)

# Default data directory: /app/data in Docker, ./data elsewhere
_DEFAULT_DATA_DIR = "/app/data" if Path("/app").exists() else "./data"


class ClientRegistry:
    """
    OAuth Client Registry with JSON storage.

    Storage: data/oauth_clients.json
    """

    def __init__(self, data_dir: str | None = None):
        data_dir = data_dir or _DEFAULT_DATA_DIR
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.clients_file = self.data_dir / "oauth_clients.json"

        # Initialize if not exists
        if not self.clients_file.exists():
            self._write_clients({})

        # Load clients into memory (small dataset)
        self.clients: dict[str, OAuthClient] = self._load_clients()

    def _read_clients(self) -> dict:
        """Read clients JSON file"""
        try:
            with open(self.clients_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading clients file: {e}")
            return {}

    def _write_clients(self, data: dict) -> bool:
        """Write clients JSON file"""
        try:
            with open(self.clients_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Error writing clients file: {e}")
            return False

    def _load_clients(self) -> dict[str, OAuthClient]:
        """Load clients from file"""
        data = self._read_clients()
        return {client_id: OAuthClient(**client_data) for client_id, client_data in data.items()}

    def _save_clients(self) -> bool:
        """Save clients to file"""
        data = {
            client_id: client.model_dump(mode="json") for client_id, client in self.clients.items()
        }
        return self._write_clients(data)

    def create_client(
        self,
        client_name: str,
        redirect_uris: list[str],
        grant_types: list[str] | None = None,
        allowed_scopes: list[str] | None = None,
        metadata: dict | None = None,
    ) -> tuple[str, str]:
        """
        Create new OAuth client.

        Returns:
            (client_id, client_secret) tuple
        """
        # Generate client_id and client_secret
        client_id = f"cmp_client_{secrets.token_urlsafe(16)}"
        client_secret = secrets.token_urlsafe(32)

        # Hash client secret
        client_secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

        # Create client
        client = OAuthClient(
            client_id=client_id,
            client_secret_hash=client_secret_hash,
            client_name=client_name,
            redirect_uris=redirect_uris,
            grant_types=grant_types or ["authorization_code", "refresh_token"],
            allowed_scopes=allowed_scopes or ["read", "write"],
            metadata=metadata or {},
        )

        # Save
        self.clients[client_id] = client
        self._save_clients()

        logger.info(f"Created OAuth client: {client_id} ({client_name})")

        # Return client_secret in plain text (only time it's visible)
        return client_id, client_secret

    def get_client(self, client_id: str) -> OAuthClient | None:
        """Get client by ID"""
        return self.clients.get(client_id)

    def list_clients(self) -> list[OAuthClient]:
        """List all clients"""
        return list(self.clients.values())

    def validate_client_secret(self, client_id: str, client_secret: str) -> bool:
        """
        Validate client secret.

        Args:
            client_id: Client ID
            client_secret: Plain text client secret

        Returns:
            True if valid, False otherwise
        """
        client = self.get_client(client_id)
        if not client:
            return False

        # Hash provided secret
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

        # Constant-time comparison
        return secrets.compare_digest(secret_hash, client.client_secret_hash)

    def delete_client(self, client_id: str) -> bool:
        """Delete OAuth client"""
        if client_id in self.clients:
            del self.clients[client_id]
            self._save_clients()
            logger.info(f"Deleted OAuth client: {client_id}")
            return True
        return False


# Singleton instance
_client_registry: ClientRegistry | None = None


def get_client_registry() -> ClientRegistry:
    """Get singleton ClientRegistry instance"""
    global _client_registry
    if _client_registry is None:
        _client_registry = ClientRegistry()
    return _client_registry
