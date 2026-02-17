"""
Site Manager - Type-safe site configuration management

Manages site configurations with Pydantic validation.
Part of Option B clean architecture refactoring.

Discovers sites from environment variables:
- {PLUGIN_TYPE}_{SITE_ID}_{CONFIG_KEY}
- {PLUGIN_TYPE}_{SITE_ID}_ALIAS (optional)

Example:
    WORDPRESS_SITE1_URL=https://example.com
    WORDPRESS_SITE1_USERNAME=admin
    WORDPRESS_SITE1_APP_PASSWORD=xxxx
    WORDPRESS_SITE2_ALIAS=myblog
"""

import logging
import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

logger = logging.getLogger(__name__)

class SiteConfig(BaseModel):
    """
    Type-safe site configuration.

    Represents configuration for a single site with validation.

    Attributes:
        site_id: Unique site identifier (e.g., 'site1')
        plugin_type: Plugin type (e.g., 'wordpress')
        alias: Optional friendly name
        config: Site-specific configuration (URL, credentials, etc.)

    Examples:
        >>> config = SiteConfig(
        ...     site_id="site1",
        ...     plugin_type="wordpress",
        ...     url="https://example.com",
        ...     username="admin",
        ...     app_password="xxxx"
        ... )
    """

    site_id: str = Field(..., description="Unique site identifier")
    plugin_type: str = Field(..., description="Plugin type (wordpress, gitea, etc)")
    alias: str | None = Field(None, description="Friendly alias for the site")

    # Common config fields (plugins may require additional fields)
    url: str | None = Field(None, description="Site URL")
    username: str | None = Field(None, description="Username for authentication")
    app_password: str | None = Field(None, description="Application password")
    container: str | None = Field(None, description="Docker container name (for WP-CLI)")

    # Allow additional fields for plugin-specific configuration
    model_config = ConfigDict(extra="allow")

    @field_validator("alias", mode="before")
    @classmethod
    def default_alias(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Set alias to site_id if not provided."""
        return v if v is not None else info.data.get("site_id")

    def get_full_id(self) -> str:
        """
        Get full site identifier.

        Returns:
            Full ID in format: plugin_type_site_id

        Examples:
            >>> config.get_full_id()
            'wordpress_site1'
        """
        return f"{self.plugin_type}_{self.site_id}"

    def get_display_name(self) -> str:
        """
        Get display name for the site.

        Returns:
            Alias if available, otherwise site_id

        Examples:
            >>> config.get_display_name()
            'myblog'  # or 'site1' if no alias
        """
        return self.alias or self.site_id

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for plugin consumption.

        Returns:
            Dictionary with all configuration

        Examples:
            >>> config_dict = config.to_dict()
            >>> plugin = WordPressPlugin(config_dict)
        """
        return self.model_dump()

class SiteManager:
    """
    Manage site configurations with type safety.

    Discovers, validates, and provides access to site configurations.

    Attributes:
        sites: Dictionary mapping plugin_type to site configurations
        aliases: Dictionary mapping aliases to (plugin_type, site_id)
        logger: Logger instance

    Examples:
        >>> manager = SiteManager()
        >>> manager.discover_sites(['wordpress', 'gitea'])
        >>> config = manager.get_site_config('wordpress', 'myblog')
        >>> sites = manager.list_sites('wordpress')
    """

    def __init__(self):
        """Initialize site manager with empty registries."""
        # Nested dict: plugin_type -> site_id/alias -> SiteConfig
        self.sites: dict[str, dict[str, SiteConfig]] = {}

        # Map aliases to full_id for quick lookup
        self.aliases: dict[str, str] = {}  # alias -> full_id

        self.logger = logging.getLogger("SiteManager")
        self.logger.info("SiteManager initialized")

    def discover_sites(self, plugin_types: list[str]) -> int:
        """
        Discover sites from environment variables.

        Scans environment for site configurations and registers them.

        Args:
            plugin_types: List of plugin types to discover (e.g., ['wordpress'])

        Returns:
            Number of sites discovered

        Examples:
            >>> count = manager.discover_sites(['wordpress', 'gitea'])
            >>> print(f"Discovered {count} sites")
        """
        self.logger.info(f"Starting site discovery for: {', '.join(plugin_types)}")

        total_discovered = 0
        for plugin_type in plugin_types:
            count = self._discover_plugin_sites(plugin_type)
            total_discovered += count

        self.logger.info(
            f"Discovery complete. Found {total_discovered} sites "
            f"across {len(plugin_types)} plugin types."
        )

        return total_discovered

    # Reserved words that should NOT be interpreted as site IDs
    RESERVED_SITE_WORDS = {
        "limit",
        "rate",
        "config",
        "debug",
        "log",
        "level",
        "mode",
        "timeout",
        "retry",
        "max",
        "min",
        "default",
        "global",
        "enabled",
        "disabled",
        "host",
        "port",
        "path",
        "key",
        "secret",
        "token",
        "advanced",
        "basic",
        "simple",
        "pro",
        "premium",
        "standard",
    }

    def _discover_plugin_sites(self, plugin_type: str) -> int:
        """
        Discover all sites for a specific plugin type.

        Args:
            plugin_type: Type of plugin (e.g., 'wordpress')

        Returns:
            Number of sites discovered for this plugin type

        Examples:
            >>> count = manager._discover_plugin_sites('wordpress')
        """
        prefix = plugin_type.upper() + "_"

        # Pattern to match: WORDPRESS_SITE1_URL, WORDPRESS_SITE2_USERNAME, etc.
        env_pattern = re.compile(f"^{prefix}([A-Z0-9_]+?)_(.+)$")

        # Find all unique site IDs
        site_ids = set()
        for env_key in os.environ.keys():
            match = env_pattern.match(env_key)
            if match:
                site_id = match.group(1).lower()
                # Skip reserved words that are not real site IDs
                if site_id not in self.RESERVED_SITE_WORDS:
                    site_ids.add(site_id)

        # Load configuration for each site
        discovered_count = 0
        for site_id in site_ids:
            try:
                config = self._load_site_config(plugin_type, site_id)
                if config:
                    self.register_site(config)
                    discovered_count += 1
            except Exception as e:
                self.logger.error(
                    f"Failed to load {plugin_type} site '{site_id}': {e}", exc_info=True
                )

        return discovered_count

    def _load_site_config(self, plugin_type: str, site_id: str) -> SiteConfig | None:
        """
        Load configuration for a site from environment.

        Args:
            plugin_type: Plugin type
            site_id: Site ID

        Returns:
            SiteConfig if successful, None if incomplete

        Examples:
            >>> config = manager._load_site_config('wordpress', 'site1')
        """
        prefix = f"{plugin_type.upper()}_{site_id.upper()}_"
        config_data = {"site_id": site_id, "plugin_type": plugin_type}

        # Collect all config keys for this site
        for env_key, env_value in os.environ.items():
            if env_key.startswith(prefix):
                # Extract config key (everything after prefix)
                config_key = env_key[len(prefix) :].lower()
                config_data[config_key] = env_value

        # Must have at least some configuration beyond site_id and plugin_type
        if len(config_data) <= 2:
            return None

        try:
            # Create and validate SiteConfig
            config = SiteConfig(**config_data)

            self.logger.debug(
                f"Loaded config for {plugin_type}/{site_id}: " f"{list(config_data.keys())}"
            )

            return config

        except Exception as e:
            self.logger.error(f"Validation failed for {plugin_type}/{site_id}: {e}", exc_info=True)
            return None

    def register_site(self, config: SiteConfig) -> None:
        """
        Register a site configuration.

        Args:
            config: Site configuration to register

        Examples:
            >>> config = SiteConfig(site_id="site1", plugin_type="wordpress", ...)
            >>> manager.register_site(config)
        """
        plugin_type = config.plugin_type

        # Initialize plugin_type dict if needed
        if plugin_type not in self.sites:
            self.sites[plugin_type] = {}

        # Register by site_id
        self.sites[plugin_type][config.site_id] = config

        # Register by alias if different from site_id
        if config.alias and config.alias != config.site_id:
            self.sites[plugin_type][config.alias] = config
            # Also register in global aliases map
            self.aliases[config.alias] = config.get_full_id()

        # Register full_id
        full_id = config.get_full_id()
        self.aliases[full_id] = full_id

        # Register site_id
        self.aliases[config.site_id] = full_id

        self.logger.info(
            f"Registered site: {full_id} " f"(alias: {config.alias or config.site_id})"
        )

    def get_site_config(self, plugin_type: str, site: str) -> SiteConfig:
        """
        Get site configuration by ID or alias.

        Args:
            plugin_type: Plugin type (e.g., 'wordpress')
            site: Site ID, alias, or full_id

        Returns:
            Site configuration

        Raises:
            ValueError: If site not found

        Examples:
            >>> config = manager.get_site_config('wordpress', 'myblog')
            >>> config = manager.get_site_config('wordpress', 'site1')
        """
        if plugin_type not in self.sites:
            # SECURITY: Don't reveal available plugin types in multi-tenant environment
            raise ValueError(
                f"No sites configured for plugin type: {plugin_type}. "
                f"Please check your environment variables."
            )

        # Try direct lookup
        config = self.sites[plugin_type].get(site)
        if config:
            return config

        # SECURITY: Don't reveal available sites in multi-tenant environment
        # Only log available sites count for debugging (not in error message)
        available_count = len(self.sites[plugin_type])
        self.logger.debug(
            f"Site '{site}' not found for {plugin_type}. "
            f"Total configured sites: {available_count}"
        )
        raise ValueError(
            f"Site '{site}' not configured for {plugin_type}. "
            f"Please verify the site alias/ID and check environment variables."
        )

    def list_sites(self, plugin_type: str) -> list[str]:
        """
        List available site IDs and aliases for a plugin type.

        Args:
            plugin_type: Plugin type

        Returns:
            List of valid site identifiers (IDs and aliases)

        Examples:
            >>> sites = manager.list_sites('wordpress')
            >>> print(sites)  # ['site1', 'site2', 'myblog']
        """
        if plugin_type not in self.sites:
            return []

        # Get unique site identifiers (both IDs and aliases)
        identifiers = set()
        for config in self.sites[plugin_type].values():
            identifiers.add(config.site_id)
            if config.alias and config.alias != config.site_id:
                identifiers.add(config.alias)

        # Remove duplicates and sort
        return sorted(set(identifiers))

    def get_sites_by_type(self, plugin_type: str) -> list[SiteConfig]:
        """
        Get all site configurations for a plugin type.

        Args:
            plugin_type: Plugin type

        Returns:
            List of site configurations

        Examples:
            >>> configs = manager.get_sites_by_type('wordpress')
            >>> for config in configs:
            ...     print(config.get_display_name())
        """
        if plugin_type not in self.sites:
            return []

        # Return unique configs (since aliases may point to same config)
        seen_site_ids = set()
        unique_configs = []

        for config in self.sites[plugin_type].values():
            if config.site_id not in seen_site_ids:
                seen_site_ids.add(config.site_id)
                unique_configs.append(config)

        return unique_configs

    def list_all_sites(self) -> list[dict[str, Any]]:
        """
        List all discovered sites across all plugin types.

        Returns:
            List of site info dictionaries

        Examples:
            >>> all_sites = manager.list_all_sites()
            >>> for site in all_sites:
            ...     print(f"{site['full_id']}: {site['alias']}")
        """
        all_sites = []
        for plugin_type in self.sites:
            for config in self.get_sites_by_type(plugin_type):
                all_sites.append(
                    {
                        "plugin_type": config.plugin_type,
                        "site_id": config.site_id,
                        "alias": config.alias,
                        "full_id": config.get_full_id(),
                    }
                )

        return all_sites

    def get_count(self) -> int:
        """
        Get total number of registered sites.

        Returns:
            Total site count

        Examples:
            >>> count = manager.get_count()
        """
        total = 0
        for plugin_type in self.sites:
            total += len(self.get_sites_by_type(plugin_type))
        return total

    def get_count_by_type(self) -> dict[str, int]:
        """
        Get site counts grouped by plugin type.

        Returns:
            Dictionary mapping plugin type to site count

        Examples:
            >>> counts = manager.get_count_by_type()
            >>> print(counts)  # {'wordpress': 4, 'gitea': 2}
        """
        return {plugin_type: len(self.get_sites_by_type(plugin_type)) for plugin_type in self.sites}

    def get_effective_path_suffix(self, full_id: str) -> str:
        """
        Get the effective path suffix for a site's endpoint.

        Uses alias if available, otherwise returns full_id.

        Args:
            full_id: The full site ID (e.g., 'wordpress_site1')

        Returns:
            Path suffix to use in endpoint URL (alias or full_id)

        Examples:
            >>> suffix = manager.get_effective_path_suffix('wordpress_site1')
            >>> print(suffix)  # 'myblog' or 'wordpress_site1'
        """
        # Parse full_id to get plugin_type and site_id
        parts = full_id.split("_", 1)
        if len(parts) != 2:
            return full_id

        plugin_type, site_id = parts

        # Try to get config
        try:
            config = self.get_site_config(plugin_type, site_id)
            # If alias exists and is different from site_id, use alias
            if config.alias and config.alias != config.site_id:
                return config.alias
            return full_id
        except ValueError:
            return full_id

    def get_alias_conflicts(self) -> dict[str, list[str]]:
        """
        Get all alias conflicts.

        Note: SiteManager doesn't track conflicts like SiteRegistry.
        This is a stub for compatibility.

        Returns:
            Empty dict (no conflict tracking in SiteManager)
        """
        return {}

    def __repr__(self) -> str:
        """String representation of site manager."""
        counts = self.get_count_by_type()
        counts_str = ", ".join(f"{k}: {v}" for k, v in counts.items())
        return f"SiteManager(total={self.get_count()}, {counts_str})"

# Singleton instance
_site_manager: SiteManager | None = None

def get_site_manager() -> SiteManager:
    """
    Get the singleton site manager instance.

    Returns:
        Global SiteManager instance

    Examples:
        >>> manager = get_site_manager()
        >>> manager.discover_sites(['wordpress'])
    """
    global _site_manager
    if _site_manager is None:
        _site_manager = SiteManager()
    return _site_manager
