"""
OAuth 2.1 Token Storage
Supports JSON files (default) and Redis (optional)
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from .schemas import AccessToken, AuthorizationCode, RefreshToken

logger = logging.getLogger(__name__)

class BaseStorage:
    """Base storage interface"""

    def save_authorization_code(self, code_data: AuthorizationCode) -> bool:
        raise NotImplementedError

    def get_authorization_code(self, code: str) -> AuthorizationCode | None:
        raise NotImplementedError

    def update_authorization_code(self, code: str, code_data: AuthorizationCode) -> bool:
        raise NotImplementedError

    def delete_authorization_code(self, code: str) -> bool:
        raise NotImplementedError

    def save_access_token(self, token_data: AccessToken) -> bool:
        raise NotImplementedError

    def get_access_token(self, token: str) -> AccessToken | None:
        raise NotImplementedError

    def save_refresh_token(self, token_data: RefreshToken) -> bool:
        raise NotImplementedError

    def get_refresh_token(self, token: str) -> RefreshToken | None:
        raise NotImplementedError

    def revoke_refresh_token(self, token: str) -> bool:
        raise NotImplementedError

class JSONStorage(BaseStorage):
    """
    JSON file storage for OAuth tokens.

    Storage structure:
        data/oauth_codes.json       - Authorization codes (short-lived)
        data/oauth_access_tokens.json   - Access tokens
        data/oauth_refresh_tokens.json  - Refresh tokens
    """

    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.codes_file = self.data_dir / "oauth_codes.json"
        self.access_tokens_file = self.data_dir / "oauth_access_tokens.json"
        self.refresh_tokens_file = self.data_dir / "oauth_refresh_tokens.json"

        # Initialize files if not exist
        for file in [self.codes_file, self.access_tokens_file, self.refresh_tokens_file]:
            if not file.exists():
                self._write_json(file, {})

    def _read_json(self, file_path: Path) -> dict[str, Any]:
        """Read JSON file"""
        try:
            with open(file_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return {}

    def _write_json(self, file_path: Path, data: dict[str, Any]) -> bool:
        """Write JSON file"""
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Error writing {file_path}: {e}")
            return False

    def save_authorization_code(self, code_data: AuthorizationCode) -> bool:
        """Save authorization code"""
        codes = self._read_json(self.codes_file)
        codes[code_data.code] = code_data.model_dump(mode="json")
        return self._write_json(self.codes_file, codes)

    def get_authorization_code(self, code: str) -> AuthorizationCode | None:
        """Get authorization code"""
        codes = self._read_json(self.codes_file)
        code_data = codes.get(code)

        if not code_data:
            return None

        # Parse and check expiry
        auth_code = AuthorizationCode(**code_data)

        if auth_code.is_expired():
            # Auto-cleanup expired codes
            self.delete_authorization_code(code)
            return None

        return auth_code

    def update_authorization_code(self, code: str, code_data: AuthorizationCode) -> bool:
        """Update authorization code (e.g., mark as used)"""
        return self.save_authorization_code(code_data)

    def delete_authorization_code(self, code: str) -> bool:
        """Delete authorization code"""
        codes = self._read_json(self.codes_file)
        if code in codes:
            del codes[code]
            return self._write_json(self.codes_file, codes)
        return False

    def save_access_token(self, token_data: AccessToken) -> bool:
        """Save access token"""
        tokens = self._read_json(self.access_tokens_file)
        tokens[token_data.token] = token_data.model_dump(mode="json")
        return self._write_json(self.access_tokens_file, tokens)

    def get_access_token(self, token: str) -> AccessToken | None:
        """Get access token"""
        tokens = self._read_json(self.access_tokens_file)
        token_data = tokens.get(token)

        if not token_data:
            return None

        access_token = AccessToken(**token_data)

        if access_token.is_expired():
            # Auto-cleanup
            tokens.pop(token, None)
            self._write_json(self.access_tokens_file, tokens)
            return None

        return access_token

    def save_refresh_token(self, token_data: RefreshToken) -> bool:
        """Save refresh token"""
        tokens = self._read_json(self.refresh_tokens_file)
        tokens[token_data.token] = token_data.model_dump(mode="json")
        return self._write_json(self.refresh_tokens_file, tokens)

    def get_refresh_token(self, token: str, include_revoked: bool = False) -> RefreshToken | None:
        """Get refresh token.

        Args:
            token: Refresh token string
            include_revoked: If True, return revoked tokens (for reuse detection)
        """
        tokens = self._read_json(self.refresh_tokens_file)
        token_data = tokens.get(token)

        if not token_data:
            return None

        refresh_token = RefreshToken(**token_data)

        if refresh_token.is_expired():
            return None

        if refresh_token.revoked and not include_revoked:
            return None

        return refresh_token

    def revoke_refresh_token(self, token: str) -> bool:
        """Revoke refresh token"""
        tokens = self._read_json(self.refresh_tokens_file)

        if token in tokens:
            tokens[token]["revoked"] = True
            return self._write_json(self.refresh_tokens_file, tokens)

        return False

    def cleanup_expired(self):
        """Cleanup expired tokens (run periodically)"""
        # Cleanup authorization codes
        codes = self._read_json(self.codes_file)
        cleaned_codes = {k: v for k, v in codes.items() if not AuthorizationCode(**v).is_expired()}
        self._write_json(self.codes_file, cleaned_codes)

        # Cleanup access tokens
        tokens = self._read_json(self.access_tokens_file)
        cleaned_tokens = {k: v for k, v in tokens.items() if not AccessToken(**v).is_expired()}
        self._write_json(self.access_tokens_file, cleaned_tokens)

        logger.info(f"Cleaned up {len(codes) - len(cleaned_codes)} expired authorization codes")
        logger.info(f"Cleaned up {len(tokens) - len(cleaned_tokens)} expired access tokens")

def get_storage() -> BaseStorage:
    """
    Get storage instance based on environment.

    Environment Variables:
        OAUTH_STORAGE_TYPE: "json" (default) | "redis"
        OAUTH_STORAGE_PATH: Path for JSON files (default: /app/data)
    """
    storage_type = os.getenv("OAUTH_STORAGE_TYPE", "json")

    if storage_type == "json":
        storage_path = os.getenv("OAUTH_STORAGE_PATH", "/app/data")
        return JSONStorage(storage_path)

    # Future: Redis support
    # elif storage_type == "redis":
    #     return RedisStorage()

    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
