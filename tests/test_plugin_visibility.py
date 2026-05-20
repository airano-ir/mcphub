"""Tests for plugin visibility control (Track F.1)."""

import os
from unittest.mock import patch

from core.plugin_visibility import (
    DEFAULT_PUBLIC_PLUGINS,
    get_public_plugin_types,
    is_plugin_public,
)


class TestGetPublicPluginTypes:
    """Tests for get_public_plugin_types()."""

    def test_default_when_env_not_set(self):
        """Returns default set when ENABLED_PLUGINS is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            result = get_public_plugin_types()
        assert result == DEFAULT_PUBLIC_PLUGINS

    def test_default_when_env_empty(self):
        """Returns default set when ENABLED_PLUGINS is empty string."""
        with patch.dict(os.environ, {"ENABLED_PLUGINS": ""}):
            result = get_public_plugin_types()
        assert result == DEFAULT_PUBLIC_PLUGINS

    def test_custom_plugins_from_env(self):
        """Reads custom plugin list from ENABLED_PLUGINS."""
        with patch.dict(os.environ, {"ENABLED_PLUGINS": "wordpress,gitea"}):
            result = get_public_plugin_types()
        assert result == {"wordpress", "gitea"}

    def test_whitespace_handling(self):
        """Strips whitespace from plugin names."""
        with patch.dict(os.environ, {"ENABLED_PLUGINS": " wordpress , supabase "}):
            result = get_public_plugin_types()
        assert result == {"wordpress", "supabase"}

    def test_case_insensitive(self):
        """Plugin names are lowercased."""
        with patch.dict(os.environ, {"ENABLED_PLUGINS": "WordPress,SUPABASE"}):
            result = get_public_plugin_types()
        assert result == {"wordpress", "supabase"}

    def test_single_plugin(self):
        """Works with a single plugin."""
        with patch.dict(os.environ, {"ENABLED_PLUGINS": "wordpress"}):
            result = get_public_plugin_types()
        assert result == {"wordpress"}

    def test_ignores_empty_entries(self):
        """Trailing commas or double commas are ignored."""
        with patch.dict(os.environ, {"ENABLED_PLUGINS": "wordpress,,supabase,"}):
            result = get_public_plugin_types()
        assert result == {"wordpress", "supabase"}


class TestIsPluginPublic:
    """Tests for is_plugin_public()."""

    def test_default_wordpress_public(self):
        """WordPress is public by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("wordpress") is True

    def test_default_woocommerce_public(self):
        """WooCommerce is public by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("woocommerce") is True

    def test_default_supabase_public(self):
        """Supabase is public by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("supabase") is True

    def test_default_gitea_public(self):
        """Gitea is public by default (since F.16)."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("gitea") is True

    def test_default_wordpress_specialist_public(self):
        """WordPress Specialist is public by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("wordpress_specialist") is True

    def test_default_n8n_public(self):
        """n8n is public by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("n8n") is True

    def test_default_coolify_public(self):
        """Coolify is public by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("coolify") is True

    def test_default_directus_and_appwrite_not_public(self):
        """Directus and Appwrite stay disabled by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("directus") is False
            assert is_plugin_public("appwrite") is False

    def test_case_insensitive_check(self):
        """Plugin type check is case insensitive."""
        with patch.dict(os.environ, {"ENABLED_PLUGINS": "wordpress"}):
            assert is_plugin_public("WordPress") is True
            assert is_plugin_public("WORDPRESS") is True

    def test_custom_env_overrides_defaults(self):
        """Custom ENABLED_PLUGINS overrides the default set."""
        with patch.dict(os.environ, {"ENABLED_PLUGINS": "gitea,n8n"}):
            assert is_plugin_public("gitea") is True
            assert is_plugin_public("n8n") is True
            assert is_plugin_public("wordpress") is False


class TestSiteApiIntegration:
    """Tests that site_api uses plugin_visibility correctly."""

    def test_get_user_credential_fields_filtered(self):
        """get_user_credential_fields only returns enabled plugins."""
        from core.site_api import get_user_credential_fields

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            fields = get_user_credential_fields()

        assert "wordpress" in fields
        assert "woocommerce" in fields
        assert "supabase" in fields
        assert "gitea" in fields
        assert "openpanel" in fields
        assert "wordpress_specialist" in fields
        assert "n8n" in fields
        assert "coolify" in fields
        assert "directus" not in fields
        assert "appwrite" not in fields

    def test_get_user_plugin_names_filtered(self):
        """get_user_plugin_names only returns enabled plugins."""
        from core.site_api import get_user_plugin_names

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            names = get_user_plugin_names()

        assert "wordpress" in names
        assert "woocommerce" in names
        assert "supabase" in names
        assert "gitea" in names
        assert "openpanel" in names
        assert "wordpress_specialist" in names
        assert "n8n" in names
        assert "coolify" in names
        assert "directus" not in names
        assert "appwrite" not in names

    def test_custom_env_changes_fields(self):
        """Custom ENABLED_PLUGINS changes which credential fields are returned."""
        from core.site_api import get_user_credential_fields

        with patch.dict(os.environ, {"ENABLED_PLUGINS": "wordpress"}):
            fields = get_user_credential_fields()

        assert "wordpress" in fields
        assert "woocommerce" not in fields
        assert "supabase" not in fields
