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

    def test_default_gitea_not_public(self):
        """Gitea is not public by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("gitea") is False

    def test_default_wordpress_advanced_not_public(self):
        """WordPress Advanced is not public by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            assert is_plugin_public("wordpress_advanced") is False

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
        assert "wordpress_advanced" not in fields
        assert "gitea" not in fields
        assert "n8n" not in fields

    def test_get_user_plugin_names_filtered(self):
        """get_user_plugin_names only returns enabled plugins."""
        from core.site_api import get_user_plugin_names

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLED_PLUGINS", None)
            names = get_user_plugin_names()

        assert "wordpress" in names
        assert "woocommerce" in names
        assert "supabase" in names
        assert "wordpress_advanced" not in names
        assert "gitea" not in names

    def test_custom_env_changes_fields(self):
        """Custom ENABLED_PLUGINS changes which credential fields are returned."""
        from core.site_api import get_user_credential_fields

        with patch.dict(os.environ, {"ENABLED_PLUGINS": "wordpress"}):
            fields = get_user_credential_fields()

        assert "wordpress" in fields
        assert "woocommerce" not in fields
        assert "supabase" not in fields
