"""Credential encryption for the Live Platform.

Provides AES-256-GCM encryption with HKDF key derivation for per-site
credential storage. Credentials are encrypted as JSON blobs and stored
in SQLite. Decryption happens only during tool execution and plaintext
is never logged.

Usage:
    encryption = get_credential_encryption()
    cipherdata = encryption.encrypt_credentials(
        {"username": "admin", "app_password": "xxxx xxxx"},
        site_id="site_abc123",
    )
    credentials = encryption.decrypt_credentials(cipherdata, site_id="site_abc123")
"""

import base64
import json
import logging
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

# Constants
_NONCE_LENGTH = 12  # 96-bit nonce for AES-GCM
_KEY_LENGTH = 32  # 256-bit key
_HKDF_SALT = b"mcphub-v1"
_FORMAT_VERSION = b"\x01"  # Wire format version for future migration support


class CredentialEncryption:
    """AES-256-GCM encryption with per-site HKDF-derived keys.

    The master key is read from the ENCRYPTION_KEY environment variable
    (base64-encoded 32-byte key). Per-site keys are derived via HKDF
    using the site_id as the info parameter, ensuring each site has a
    unique encryption key.

    Storage format: version (1 byte) || nonce (12 bytes) || ciphertext || tag (16 bytes)
    """

    def __init__(self, encryption_key: str | None = None) -> None:
        """Initialize credential encryption.

        Args:
            encryption_key: Base64-encoded 32-byte key. If not provided,
                reads from the ENCRYPTION_KEY environment variable.

        Raises:
            ValueError: If the encryption key is missing or invalid.
        """
        raw_key = encryption_key or os.getenv("ENCRYPTION_KEY")

        if not raw_key:
            raise ValueError(
                "ENCRYPTION_KEY is required. Set it as an environment variable "
                "or pass it directly. Generate one with: "
                'python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"'
            )

        try:
            self._master_key = base64.b64decode(raw_key)
        except Exception as exc:
            raise ValueError("ENCRYPTION_KEY must be a valid base64-encoded string.") from exc

        if len(self._master_key) != _KEY_LENGTH:
            raise ValueError(
                f"ENCRYPTION_KEY must decode to exactly {_KEY_LENGTH} bytes, "
                f"got {len(self._master_key)} bytes."
            )

        logger.info("Credential encryption initialized")

    def _derive_key(self, site_id: str) -> bytes:
        """Derive a per-site encryption key using HKDF.

        Args:
            site_id: Unique identifier for the site.

        Returns:
            32-byte derived key for the given site.
        """
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=_KEY_LENGTH,
            salt=_HKDF_SALT,
            info=site_id.encode("utf-8"),
        )
        return hkdf.derive(self._master_key)

    def encrypt(self, plaintext: str, site_id: str) -> bytes:
        """Encrypt a plaintext string for a specific site.

        Args:
            plaintext: The string to encrypt.
            site_id: Site identifier used for key derivation.

        Returns:
            Encrypted bytes: version (1) || nonce (12) || ciphertext || tag (16).
        """
        derived_key = self._derive_key(site_id)
        aesgcm = AESGCM(derived_key)
        nonce = os.urandom(_NONCE_LENGTH)
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return _FORMAT_VERSION + nonce + ciphertext_with_tag

    def decrypt(self, cipherdata: bytes, site_id: str) -> str:
        """Decrypt cipherdata for a specific site.

        Args:
            cipherdata: Encrypted bytes (nonce || ciphertext || tag).
            site_id: Site identifier used for key derivation.

        Returns:
            Original plaintext string.

        Raises:
            cryptography.exceptions.InvalidTag: If decryption fails
                (wrong key, tampered data, or wrong site_id).
            ValueError: If cipherdata is too short or has unsupported version.
        """
        # Minimum: 1 (version) + 12 (nonce) + 16 (tag) = 29 bytes
        min_length = 1 + _NONCE_LENGTH + 16
        if len(cipherdata) < min_length:
            raise ValueError(
                f"Cipherdata too short: expected at least {min_length} bytes, "
                f"got {len(cipherdata)}."
            )

        version = cipherdata[:1]
        if version != _FORMAT_VERSION:
            raise ValueError(
                f"Unsupported encryption format version: {version!r}. "
                f"Expected {_FORMAT_VERSION!r}."
            )

        nonce = cipherdata[1 : 1 + _NONCE_LENGTH]
        ciphertext_with_tag = cipherdata[1 + _NONCE_LENGTH :]

        derived_key = self._derive_key(site_id)
        aesgcm = AESGCM(derived_key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return plaintext_bytes.decode("utf-8")

    def encrypt_credentials(self, credentials: dict, site_id: str) -> bytes:
        """Encrypt a credentials dictionary for a specific site.

        The dictionary is serialized to JSON, then encrypted.

        Args:
            credentials: Dictionary of credentials (e.g., username, password).
            site_id: Site identifier used for key derivation.

        Returns:
            Encrypted bytes.
        """
        json_str = json.dumps(credentials, separators=(",", ":"), sort_keys=True)
        return self.encrypt(json_str, site_id)

    def decrypt_credentials(self, cipherdata: bytes, site_id: str) -> dict:
        """Decrypt cipherdata back to a credentials dictionary.

        Args:
            cipherdata: Encrypted bytes from encrypt_credentials.
            site_id: Site identifier used for key derivation.

        Returns:
            Original credentials dictionary.

        Raises:
            cryptography.exceptions.InvalidTag: If decryption fails.
            json.JSONDecodeError: If decrypted data is not valid JSON.
        """
        json_str = self.decrypt(cipherdata, site_id)
        return json.loads(json_str)

    def encrypt_for_scope(self, plaintext: str, scope: str) -> bytes:
        """Encrypt a plaintext string using an arbitrary HKDF scope string.

        Used when the encrypted value is not a per-site credentials blob but
        still needs per-key isolation (e.g. per-site AI provider API keys
        where scope is ``site_provider:{site_id}:{provider}``).

        Args:
            plaintext: The string to encrypt.
            scope: Scope string used as HKDF info for key derivation. Any
                caller reading back the ciphertext must pass the same scope.

        Returns:
            Encrypted bytes (same wire format as :meth:`encrypt`).
        """
        return self.encrypt(plaintext, scope)

    def decrypt_for_scope(self, cipherdata: bytes, scope: str) -> str:
        """Decrypt cipherdata produced by :meth:`encrypt_for_scope`.

        Args:
            cipherdata: Encrypted bytes.
            scope: Scope string — must exactly match what was used to encrypt.

        Returns:
            Original plaintext string.
        """
        return self.decrypt(cipherdata, scope)


# Global credential encryption instance
_credential_encryption: CredentialEncryption | None = None


def initialize_credential_encryption(
    encryption_key: str | None = None,
) -> CredentialEncryption:
    """Initialize the global credential encryption instance.

    Args:
        encryption_key: Base64-encoded 32-byte key. If not provided,
            reads from the ENCRYPTION_KEY environment variable.

    Returns:
        The initialized CredentialEncryption instance.
    """
    global _credential_encryption
    _credential_encryption = CredentialEncryption(encryption_key)
    return _credential_encryption


def get_credential_encryption() -> CredentialEncryption:
    """Get the global credential encryption instance.

    Lazily initializes from the ENCRYPTION_KEY environment variable
    if not already initialized via initialize_credential_encryption().
    """
    global _credential_encryption
    if _credential_encryption is None:
        _credential_encryption = CredentialEncryption()
    return _credential_encryption
