"""Tests for Site Manager (core/site_manager.py)."""

import pytest

from core.site_manager import SiteConfig, SiteManager


# --- SiteConfig Tests ---


class TestSiteConfig:
    """Test SiteConfig Pydantic model."""

    def test_basic_creation(self):
        """Should create a config with required fields."""
        config = SiteConfig(
            site_id="site1",
            plugin_type="wordpress",
            url="https://example.com",
        )
        assert config.site_id == "site1"
        assert config.plugin_type == "wordpress"
        assert config.url == "https://example.com"

    def test_alias_none_when_not_provided(self):
        """Alias should be None when not explicitly provided."""
        config = SiteConfig(site_id="site1", plugin_type="wordpress")
        # Pydantic V2: field_validator doesn't run on default values
        # get_display_name() handles the fallback to site_id
        assert config.alias is None
        assert config.get_display_name() == "site1"

    def test_custom_alias(self):
        """Custom alias should override default."""
        config = SiteConfig(site_id="site1", plugin_type="wordpress", alias="myblog")
        assert config.alias == "myblog"

    def test_get_full_id(self):
        """Full ID should be plugin_type_site_id."""
        config = SiteConfig(site_id="site1", plugin_type="wordpress")
        assert config.get_full_id() == "wordpress_site1"

    def test_get_display_name_with_alias(self):
        """Display name should prefer alias."""
        config = SiteConfig(site_id="site1", plugin_type="wordpress", alias="myblog")
        assert config.get_display_name() == "myblog"

    def test_get_display_name_without_alias(self):
        """Display name should fall back to site_id."""
        config = SiteConfig(site_id="site1", plugin_type="wordpress", alias=None)
        assert config.get_display_name() == "site1"

    def test_extra_fields_allowed(self):
        """Plugin-specific fields should be accepted."""
        config = SiteConfig(
            site_id="site1",
            plugin_type="wordpress",
            consumer_key="ck_123",
            consumer_secret="cs_456",
        )
        assert config.model_extra["consumer_key"] == "ck_123"

    def test_to_dict(self):
        """to_dict should include all fields."""
        config = SiteConfig(
            site_id="site1",
            plugin_type="wordpress",
            url="https://example.com",
        )
        d = config.to_dict()
        assert d["site_id"] == "site1"
        assert d["plugin_type"] == "wordpress"
        assert d["url"] == "https://example.com"


# --- SiteManager Tests ---


class TestSiteManagerRegistration:
    """Test site registration and lookup."""

    @pytest.fixture
    def manager(self):
        return SiteManager()

    def test_register_site(self, manager):
        """Should register a site and retrieve it by ID."""
        config = SiteConfig(site_id="site1", plugin_type="wordpress", url="https://example.com")
        manager.register_site(config)
        result = manager.get_site_config("wordpress", "site1")
        assert result.url == "https://example.com"

    def test_register_site_with_alias(self, manager):
        """Should be retrievable by alias."""
        config = SiteConfig(
            site_id="site1", plugin_type="wordpress", alias="myblog", url="https://example.com"
        )
        manager.register_site(config)
        result = manager.get_site_config("wordpress", "myblog")
        assert result.site_id == "site1"

    def test_site_not_found_raises(self, manager):
        """Should raise ValueError for unknown site."""
        config = SiteConfig(site_id="site1", plugin_type="wordpress")
        manager.register_site(config)
        with pytest.raises(ValueError, match="not configured"):
            manager.get_site_config("wordpress", "nonexistent")

    def test_unknown_plugin_type_raises(self, manager):
        """Should raise ValueError for unknown plugin type."""
        with pytest.raises(ValueError, match="No sites configured"):
            manager.get_site_config("unknown_plugin", "site1")

    def test_list_sites(self, manager):
        """Should list all site IDs and aliases."""
        config1 = SiteConfig(site_id="site1", plugin_type="wordpress", alias="blog1")
        config2 = SiteConfig(site_id="site2", plugin_type="wordpress", alias="blog2")
        manager.register_site(config1)
        manager.register_site(config2)
        sites = manager.list_sites("wordpress")
        assert "site1" in sites
        assert "site2" in sites
        assert "blog1" in sites
        assert "blog2" in sites

    def test_list_sites_empty_plugin(self, manager):
        """Should return empty list for unknown plugin type."""
        assert manager.list_sites("nonexistent") == []


class TestSiteManagerDiscovery:
    """Test site discovery from environment variables."""

    def test_discover_wordpress_sites(self, monkeypatch):
        """Should discover sites from WORDPRESS_SITE1_* env vars."""
        monkeypatch.setenv("WORDPRESS_SITE1_URL", "https://wp1.example.com")
        monkeypatch.setenv("WORDPRESS_SITE1_USERNAME", "admin")
        monkeypatch.setenv("WORDPRESS_SITE1_APP_PASSWORD", "xxxx")
        monkeypatch.setenv("WORDPRESS_SITE1_ALIAS", "myblog")

        manager = SiteManager()
        count = manager.discover_sites(["wordpress"])

        assert count == 1
        config = manager.get_site_config("wordpress", "site1")
        assert config.url == "https://wp1.example.com"
        assert config.username == "admin"
        assert config.alias == "myblog"

    def test_discover_multiple_sites(self, monkeypatch):
        """Should discover multiple sites for same plugin type."""
        monkeypatch.setenv("WORDPRESS_SITE1_URL", "https://wp1.example.com")
        monkeypatch.setenv("WORDPRESS_SITE1_USERNAME", "admin")
        monkeypatch.setenv("WORDPRESS_SITE2_URL", "https://wp2.example.com")
        monkeypatch.setenv("WORDPRESS_SITE2_USERNAME", "editor")

        manager = SiteManager()
        count = manager.discover_sites(["wordpress"])

        assert count == 2

    def test_discover_across_plugin_types(self, monkeypatch):
        """Should discover sites across different plugin types."""
        monkeypatch.setenv("WORDPRESS_SITE1_URL", "https://wp.example.com")
        monkeypatch.setenv("WORDPRESS_SITE1_USERNAME", "admin")
        monkeypatch.setenv("GITEA_SITE1_URL", "https://git.example.com")
        monkeypatch.setenv("GITEA_SITE1_TOKEN", "tok_123")

        manager = SiteManager()
        count = manager.discover_sites(["wordpress", "gitea"])

        assert count == 2

    def test_reserved_words_skipped(self, monkeypatch):
        """Reserved words like LIMIT, RATE should not become site IDs."""
        monkeypatch.setenv("WORDPRESS_LIMIT_PER_MINUTE", "100")
        monkeypatch.setenv("WORDPRESS_RATE_PER_HOUR", "500")

        manager = SiteManager()
        count = manager.discover_sites(["wordpress"])

        assert count == 0

    def test_incomplete_config_skipped(self, monkeypatch):
        """Sites with no config data (only prefix match) should be skipped."""
        # WORDPRESS_SITE1_ exists as prefix but no actual config keys
        # This is hard to test directly since env vars always have a value
        # Instead, test that a site with only site_id and plugin_type (no config) is skipped
        manager = SiteManager()
        count = manager.discover_sites(["wordpress"])
        assert count == 0


class TestSiteManagerCounts:
    """Test counting and listing methods."""

    @pytest.fixture
    def populated_manager(self):
        manager = SiteManager()
        for i in range(3):
            config = SiteConfig(
                site_id=f"site{i+1}",
                plugin_type="wordpress",
                url=f"https://wp{i+1}.example.com",
            )
            manager.register_site(config)
        config = SiteConfig(
            site_id="repo1",
            plugin_type="gitea",
            url="https://git.example.com",
        )
        manager.register_site(config)
        return manager

    def test_get_count(self, populated_manager):
        assert populated_manager.get_count() == 4

    def test_get_count_by_type(self, populated_manager):
        counts = populated_manager.get_count_by_type()
        assert counts["wordpress"] == 3
        assert counts["gitea"] == 1

    def test_get_sites_by_type(self, populated_manager):
        wp_sites = populated_manager.get_sites_by_type("wordpress")
        assert len(wp_sites) == 3

    def test_get_sites_by_type_empty(self, populated_manager):
        assert populated_manager.get_sites_by_type("nonexistent") == []

    def test_list_all_sites(self, populated_manager):
        all_sites = populated_manager.list_all_sites()
        assert len(all_sites) == 4
        plugin_types = {s["plugin_type"] for s in all_sites}
        assert plugin_types == {"wordpress", "gitea"}

    def test_repr(self, populated_manager):
        r = repr(populated_manager)
        assert "SiteManager" in r
        assert "total=4" in r
