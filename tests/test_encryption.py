"""Tests for Credential Encryption (core/encryption.py)."""

import base64
import json
import os

import pytest
from cryptography.exceptions import InvalidTag

from core.encryption import (
    CredentialEncryption,
    get_credential_encryption,
    initialize_credential_encryption,
)

# A valid base64-encoded 32-byte key for testing
TEST_KEY = base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def encryption():
    """Create a CredentialEncryption instance with a test key."""
    return CredentialEncryption(encryption_key=TEST_KEY)


@pytest.fixture
def _clear_singleton():
    """Reset the global singleton before and after each test that uses it."""
    import core.encryption as mod

    original = mod._credential_encryption
    mod._credential_encryption = None
    yield
    mod._credential_encryption = original


@pytest.mark.unit
class TestEncryptDecrypt:
    """Test basic encrypt/decrypt round-trips."""

    def test_round_trip(self, encryption):
        """Encrypt then decrypt should return the original plaintext."""
        plaintext = "Hello, World!"
        site_id = "site_001"

        cipherdata = encryption.encrypt(plaintext, site_id)
        result = encryption.decrypt(cipherdata, site_id)

        assert result == plaintext

    def test_credentials_round_trip(self, encryption):
        """encrypt_credentials then decrypt_credentials should return the same dict."""
        credentials = {
            "username": "admin",
            "app_password": "xxxx xxxx xxxx xxxx",
            "api_key": "sk-1234567890",
        }
        site_id = "site_002"

        cipherdata = encryption.encrypt_credentials(credentials, site_id)
        result = encryption.decrypt_credentials(cipherdata, site_id)

        assert result == credentials

    def test_empty_credentials(self, encryption):
        """Empty dict should encrypt and decrypt correctly."""
        credentials = {}
        site_id = "site_empty"

        cipherdata = encryption.encrypt_credentials(credentials, site_id)
        result = encryption.decrypt_credentials(cipherdata, site_id)

        assert result == {}

    def test_unicode_credentials(self, encryption):
        """Non-ASCII characters in credentials should survive round-trip."""
        credentials = {
            "username": "\u06a9\u0627\u0631\u0628\u0631",
            "password": "\u0631\u0645\u0632\u0639\u0628\u0648\u0631-\u0627\u06cc\u0645\u0646",
            "display_name": "\u5f20\u4e09\u7684\u535a\u5ba2",
            "notes": "Emoji \u2764\ufe0f test \U0001f680",
        }
        site_id = "site_unicode"

        cipherdata = encryption.encrypt_credentials(credentials, site_id)
        result = encryption.decrypt_credentials(cipherdata, site_id)

        assert result == credentials

    def test_large_payload(self, encryption):
        """A large JSON payload (~10KB) should encrypt and decrypt correctly."""
        credentials = {f"key_{i}": f"value_{i}_{'x' * 100}" for i in range(85)}
        json_size = len(json.dumps(credentials))
        assert json_size > 10000, f"Payload should be >10KB, got {json_size}"

        site_id = "site_large"
        cipherdata = encryption.encrypt_credentials(credentials, site_id)
        result = encryption.decrypt_credentials(cipherdata, site_id)

        assert result == credentials

    def test_empty_string_encrypt_decrypt(self, encryption):
        """Empty string should encrypt and decrypt correctly."""
        cipherdata = encryption.encrypt("", "site_empty_str")
        result = encryption.decrypt(cipherdata, "site_empty_str")
        assert result == ""


@pytest.mark.unit
class TestSiteIsolation:
    """Test that different site_ids produce different ciphertext and keys."""

    def test_different_site_ids_produce_different_ciphertext(self, encryption):
        """Same plaintext encrypted with different site_ids should differ."""
        plaintext = "same-secret-value"
        cipher_a = encryption.encrypt(plaintext, "site_alpha")
        cipher_b = encryption.encrypt(plaintext, "site_beta")

        # Ciphertext should differ (different derived keys + different nonces)
        assert cipher_a != cipher_b

    def test_wrong_site_id_fails_to_decrypt(self, encryption):
        """Decrypting with the wrong site_id should raise InvalidTag."""
        plaintext = "secret-data"
        cipherdata = encryption.encrypt(plaintext, "correct_site")

        with pytest.raises(InvalidTag):
            encryption.decrypt(cipherdata, "wrong_site")

    def test_wrong_site_id_fails_credentials(self, encryption):
        """decrypt_credentials with wrong site_id should raise InvalidTag."""
        credentials = {"username": "admin", "password": "secret"}
        cipherdata = encryption.encrypt_credentials(credentials, "correct_site")

        with pytest.raises(InvalidTag):
            encryption.decrypt_credentials(cipherdata, "wrong_site")


@pytest.mark.unit
class TestTampering:
    """Test that tampered ciphertext is detected."""

    def test_tampered_ciphertext_fails(self, encryption):
        """Modifying a byte in the ciphertext should cause decryption to fail."""
        plaintext = "sensitive-data"
        site_id = "site_tamper"

        cipherdata = encryption.encrypt(plaintext, site_id)

        # Tamper with a byte in the ciphertext portion (after version + nonce)
        tampered = bytearray(cipherdata)
        tampered[16] ^= 0xFF  # Flip bits in a ciphertext byte
        tampered = bytes(tampered)

        with pytest.raises(InvalidTag):
            encryption.decrypt(tampered, site_id)

    def test_tampered_nonce_fails(self, encryption):
        """Modifying the nonce should cause decryption to fail."""
        plaintext = "sensitive-data"
        site_id = "site_nonce_tamper"

        cipherdata = encryption.encrypt(plaintext, site_id)

        tampered = bytearray(cipherdata)
        tampered[1] ^= 0xFF  # Flip bits in the nonce (byte 1, after version byte)
        tampered = bytes(tampered)

        with pytest.raises(InvalidTag):
            encryption.decrypt(tampered, site_id)

    def test_truncated_cipherdata_fails(self, encryption):
        """Truncated cipherdata should raise ValueError."""
        with pytest.raises(ValueError, match="too short"):
            encryption.decrypt(b"short", "site_trunc")

    def test_unsupported_version_fails(self, encryption):
        """Cipherdata with wrong version byte should raise ValueError."""
        cipherdata = encryption.encrypt("test", "site_ver")
        # Replace version byte with 0x99
        bad_version = b"\x99" + cipherdata[1:]
        with pytest.raises(ValueError, match="Unsupported encryption format version"):
            encryption.decrypt(bad_version, "site_ver")


@pytest.mark.unit
class TestKeyValidation:
    """Test encryption key validation."""

    def test_missing_key_raises_valueerror(self, monkeypatch):
        """Missing ENCRYPTION_KEY should raise ValueError."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

        with pytest.raises(ValueError, match="ENCRYPTION_KEY is required"):
            CredentialEncryption()

    def test_invalid_base64_raises_valueerror(self):
        """Non-base64 key should raise ValueError."""
        with pytest.raises(ValueError, match="valid base64"):
            CredentialEncryption(encryption_key="not-valid-base64!!!")

    def test_wrong_length_key_raises_valueerror(self):
        """Key that decodes to wrong number of bytes should raise ValueError."""
        short_key = base64.b64encode(b"too-short").decode()
        with pytest.raises(ValueError, match="exactly 32 bytes"):
            CredentialEncryption(encryption_key=short_key)

    def test_16_byte_key_raises_valueerror(self):
        """A 16-byte key (AES-128) should be rejected; we require 32 bytes."""
        key_16 = base64.b64encode(os.urandom(16)).decode()
        with pytest.raises(ValueError, match="exactly 32 bytes"):
            CredentialEncryption(encryption_key=key_16)

    def test_valid_key_from_env(self, monkeypatch):
        """ENCRYPTION_KEY from env should be accepted when valid."""
        key = base64.b64encode(os.urandom(32)).decode()
        monkeypatch.setenv("ENCRYPTION_KEY", key)

        enc = CredentialEncryption()
        # Should work without error
        cipherdata = enc.encrypt("test", "site")
        assert enc.decrypt(cipherdata, "site") == "test"


@pytest.mark.unit
class TestKeyDerivation:
    """Test HKDF key derivation properties."""

    def test_deterministic(self, encryption):
        """Same site_id should always produce the same derived key."""
        key_a = encryption._derive_key("site_deterministic")
        key_b = encryption._derive_key("site_deterministic")
        assert key_a == key_b

    def test_different_sites_different_keys(self, encryption):
        """Different site_ids should produce different derived keys."""
        key_a = encryption._derive_key("site_one")
        key_b = encryption._derive_key("site_two")
        assert key_a != key_b

    def test_derived_key_length(self, encryption):
        """Derived key should be 32 bytes."""
        key = encryption._derive_key("any_site")
        assert len(key) == 32


@pytest.mark.unit
class TestNonceUniqueness:
    """Test that random nonces ensure ciphertext uniqueness."""

    def test_same_plaintext_different_ciphertext(self, encryption):
        """Two encryptions of the same plaintext should produce different ciphertext."""
        plaintext = "identical-value"
        site_id = "site_nonce"

        cipher_a = encryption.encrypt(plaintext, site_id)
        cipher_b = encryption.encrypt(plaintext, site_id)

        # Both should decrypt to the same value
        assert encryption.decrypt(cipher_a, site_id) == plaintext
        assert encryption.decrypt(cipher_b, site_id) == plaintext

        # But the ciphertext should differ (different random nonces)
        assert cipher_a != cipher_b

    def test_nonce_is_12_bytes(self, encryption):
        """The nonce prefix should be exactly 12 bytes (after version byte)."""
        cipherdata = encryption.encrypt("test", "site_nonce_len")
        # Minimum size: 1 (version) + 12 (nonce) + 0 (empty plaintext encrypted) + 16 (tag)
        assert len(cipherdata) >= 29
        # Version byte is 0x01
        assert cipherdata[0:1] == b"\x01"


@pytest.mark.unit
class TestSingleton:
    """Test the module-level singleton getter."""

    @pytest.mark.usefixtures("_clear_singleton")
    def test_get_credential_encryption_returns_instance(self, monkeypatch):
        """get_credential_encryption should return a CredentialEncryption instance."""
        key = base64.b64encode(os.urandom(32)).decode()
        monkeypatch.setenv("ENCRYPTION_KEY", key)

        enc = get_credential_encryption()
        assert isinstance(enc, CredentialEncryption)

    @pytest.mark.usefixtures("_clear_singleton")
    def test_singleton_returns_same_instance(self, monkeypatch):
        """Calling get_credential_encryption twice should return the same object."""
        key = base64.b64encode(os.urandom(32)).decode()
        monkeypatch.setenv("ENCRYPTION_KEY", key)

        enc_a = get_credential_encryption()
        enc_b = get_credential_encryption()
        assert enc_a is enc_b

    @pytest.mark.usefixtures("_clear_singleton")
    def test_singleton_raises_without_key(self, monkeypatch):
        """get_credential_encryption should raise ValueError if ENCRYPTION_KEY is missing."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

        with pytest.raises(ValueError, match="ENCRYPTION_KEY is required"):
            get_credential_encryption()

    @pytest.mark.usefixtures("_clear_singleton")
    def test_initialize_with_explicit_key(self, monkeypatch):
        """initialize_credential_encryption should accept an explicit key."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        key = base64.b64encode(os.urandom(32)).decode()

        enc = initialize_credential_encryption(key)
        assert isinstance(enc, CredentialEncryption)
        # Should be the same as get_credential_encryption now
        assert get_credential_encryption() is enc
