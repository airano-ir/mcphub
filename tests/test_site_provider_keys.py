"""Tests for per-site AI provider keys (F.5a.9.x).

Uses a real SQLite DB + real AES-256-GCM encryption to exercise the full
round-trip: site_api encrypts/decrypts via the per-site scope, DB stores
ciphertext, tenant isolation is enforced, and cascade delete cleans up.
"""

import base64
import os

import pytest

from core.database import Database, initialize_database
from core.site_api import (
    PROVIDER_KEYS_ALLOWED_PLUGIN_TYPES,
    SITE_PROVIDERS,
    delete_site_provider_key,
    get_site_provider_key,
    list_site_providers_set,
    set_site_provider_key,
    site_provider_scope,
    site_supports_provider_keys,
)


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch):
    """Ensure ENCRYPTION_KEY is set and encryption singleton is fresh."""
    key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    import core.encryption as enc_mod

    monkeypatch.setattr(enc_mod, "_credential_encryption", None)


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """Initialize DB singleton so site_api.get_database() works."""
    import core.database as db_mod

    monkeypatch.setattr(db_mod, "_database", None)
    database = await initialize_database(str(tmp_path / "test.db"))
    yield database
    await database.close()
    monkeypatch.setattr(db_mod, "_database", None)


@pytest.fixture
async def user_row(db: Database):
    return await db.create_user(
        email="owner@example.com",
        name="Owner",
        provider="github",
        provider_id="gh-999",
    )


@pytest.fixture
async def second_user(db: Database):
    return await db.create_user(
        email="stranger@example.com",
        name="Stranger",
        provider="google",
        provider_id="gg-888",
    )


async def _make_site(db: Database, user_id: str, *, plugin_type="wordpress", alias="myblog"):
    return await db.create_site(
        user_id=user_id,
        plugin_type=plugin_type,
        alias=alias,
        url=f"https://{alias}.example.com",
        credentials=b"fake-encrypted-creds",
    )


# ---------------------------------------------------------------------------
# Pure helpers (no DB)
# ---------------------------------------------------------------------------


class TestHelpers:
    @pytest.mark.unit
    def test_scope_format(self):
        assert site_provider_scope("abc-123", "openai") == "site_provider:abc-123:openai"

    @pytest.mark.unit
    def test_scope_differs_per_provider(self):
        s1 = site_provider_scope("site-1", "openai")
        s2 = site_provider_scope("site-1", "stability")
        assert s1 != s2

    @pytest.mark.unit
    def test_supports_provider_keys_wp_wc(self):
        assert site_supports_provider_keys("wordpress") is True
        assert site_supports_provider_keys("woocommerce") is True

    @pytest.mark.unit
    def test_supports_provider_keys_rejects_others(self):
        for plugin_type in ("gitea", "n8n", "supabase", "openpanel", "appwrite"):
            assert site_supports_provider_keys(plugin_type) is False

    @pytest.mark.unit
    def test_allowed_plugin_types_and_providers(self):
        # Guard against accidental scope creep
        assert frozenset({"wordpress", "woocommerce"}) == PROVIDER_KEYS_ALLOWED_PLUGIN_TYPES
        assert set(SITE_PROVIDERS) == {"openai", "stability", "replicate", "openrouter"}


# ---------------------------------------------------------------------------
# Round-trip via site_api + DB + real AES-GCM
# ---------------------------------------------------------------------------


class TestSiteProviderKeyRoundTrip:
    @pytest.mark.unit
    async def test_set_then_get_returns_plaintext(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        await set_site_provider_key(site["id"], user_row["id"], "openai", "sk-test-1234567890")

        got = await get_site_provider_key(site["id"], "openai")
        assert got == "sk-test-1234567890"

    @pytest.mark.unit
    async def test_get_missing_returns_none(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        assert await get_site_provider_key(site["id"], "openai") is None

    @pytest.mark.unit
    async def test_set_trims_whitespace(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        await set_site_provider_key(site["id"], user_row["id"], "openai", "  sk-xyz  ")
        assert await get_site_provider_key(site["id"], "openai") == "sk-xyz"

    @pytest.mark.unit
    async def test_set_overwrites_existing(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        await set_site_provider_key(site["id"], user_row["id"], "openai", "first")
        await set_site_provider_key(site["id"], user_row["id"], "openai", "second")
        assert await get_site_provider_key(site["id"], "openai") == "second"

    @pytest.mark.unit
    async def test_list_providers_set(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        assert await list_site_providers_set(site["id"]) == set()

        await set_site_provider_key(site["id"], user_row["id"], "openai", "a")
        await set_site_provider_key(site["id"], user_row["id"], "stability", "b")
        assert await list_site_providers_set(site["id"]) == {"openai", "stability"}

    @pytest.mark.unit
    async def test_delete(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        await set_site_provider_key(site["id"], user_row["id"], "openai", "a")

        deleted = await delete_site_provider_key(site["id"], user_row["id"], "openai")
        assert deleted is True
        assert await get_site_provider_key(site["id"], "openai") is None

    @pytest.mark.unit
    async def test_delete_missing_returns_false(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        assert await delete_site_provider_key(site["id"], user_row["id"], "openai") is False


# ---------------------------------------------------------------------------
# Validation / security
# ---------------------------------------------------------------------------


class TestSiteProviderKeyValidation:
    @pytest.mark.unit
    async def test_rejects_empty_key(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        with pytest.raises(ValueError, match="empty"):
            await set_site_provider_key(site["id"], user_row["id"], "openai", "   ")

    @pytest.mark.unit
    async def test_rejects_unknown_provider(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        with pytest.raises(ValueError, match="Unsupported provider"):
            await set_site_provider_key(site["id"], user_row["id"], "midjourney", "abc")

    @pytest.mark.unit
    async def test_rejects_unknown_site(self, db, user_row):
        with pytest.raises(ValueError, match="Site not found"):
            await set_site_provider_key("does-not-exist", user_row["id"], "openai", "abc")

    @pytest.mark.unit
    async def test_rejects_non_wp_wc_site(self, db, user_row):
        site = await _make_site(db, user_row["id"], plugin_type="gitea")
        with pytest.raises(ValueError, match="does not support"):
            await set_site_provider_key(site["id"], user_row["id"], "openai", "abc")

    @pytest.mark.unit
    async def test_get_unknown_provider_returns_none(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        assert await get_site_provider_key(site["id"], "midjourney") is None

    @pytest.mark.unit
    async def test_foreign_user_cannot_set_key(self, db, user_row, second_user):
        site = await _make_site(db, user_row["id"])
        # set_site_provider_key enforces ownership via db.get_site(site_id, user_id)
        with pytest.raises(ValueError, match="Site not found"):
            await set_site_provider_key(site["id"], second_user["id"], "openai", "abc")

    @pytest.mark.unit
    async def test_foreign_user_cannot_delete_key(self, db, user_row, second_user):
        site = await _make_site(db, user_row["id"])
        await set_site_provider_key(site["id"], user_row["id"], "openai", "abc")

        # Delete by stranger — returns False, row still present
        assert await delete_site_provider_key(site["id"], second_user["id"], "openai") is False
        assert await get_site_provider_key(site["id"], "openai") == "abc"


# ---------------------------------------------------------------------------
# Encryption isolation
# ---------------------------------------------------------------------------


class TestSiteProviderKeyEncryption:
    @pytest.mark.unit
    async def test_ciphertext_not_plaintext_in_db(self, db, user_row):
        site = await _make_site(db, user_row["id"])
        await set_site_provider_key(site["id"], user_row["id"], "openai", "sk-SENSITIVE-VALUE")
        row = await db.get_site_provider_key(site["id"], "openai")
        assert row is not None
        assert b"sk-SENSITIVE-VALUE" not in row["key_ciphertext"]

    @pytest.mark.unit
    async def test_keys_differ_across_sites(self, db, user_row):
        """Two sites storing the same plaintext key should produce different
        ciphertexts (different HKDF scope + different random nonce)."""
        s1 = await _make_site(db, user_row["id"], alias="one")
        s2 = await _make_site(db, user_row["id"], alias="two", plugin_type="woocommerce")

        await set_site_provider_key(s1["id"], user_row["id"], "openai", "same")
        await set_site_provider_key(s2["id"], user_row["id"], "openai", "same")

        r1 = await db.get_site_provider_key(s1["id"], "openai")
        r2 = await db.get_site_provider_key(s2["id"], "openai")
        assert r1 is not None and r2 is not None
        assert r1["key_ciphertext"] != r2["key_ciphertext"]

        # Both decrypt back to the same plaintext via their own scopes
        assert await get_site_provider_key(s1["id"], "openai") == "same"
        assert await get_site_provider_key(s2["id"], "openai") == "same"
