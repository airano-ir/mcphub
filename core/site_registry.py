"""
Site Registry

Manages site configurations discovered from environment variables.
Supports multi-site setups with aliases and dynamic discovery.
"""

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


class SiteInfo:
    """Information about a single site."""

    def __init__(
        self, plugin_type: str, site_id: str, config: dict[str, Any], alias: str | None = None
    ):
        """
        Initialize site information.

        Args:
            plugin_type: Type of plugin (e.g., 'wordpress')
            site_id: Site identifier (e.g., 'site1')
            config: Site configuration from environment
            alias: Optional friendly alias for the site
        """
        self.plugin_type = plugin_type
        self.site_id = site_id
        self.config = config
        self.alias = alias or site_id

    def get_full_id(self) -> str:
        """Get full site identifier: plugin_type_site_id"""
        return f"{self.plugin_type}_{self.site_id}"

    def get_display_name(self) -> str:
        """Get display name (alias if available, otherwise site_id)"""
        return self.alias

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "plugin_type": self.plugin_type,
            "site_id": self.site_id,
            "alias": self.alias,
            "full_id": self.get_full_id(),
            "config_keys": list(self.config.keys()),
        }


class SiteRegistry:
    """
    Registry for managing site configurations across plugin types.

    Discovers sites from environment variables:
    - {PLUGIN_TYPE}_{SITE_ID}_{CONFIG_KEY}
    - {PLUGIN_TYPE}_{SITE_ID}_ALIAS (optional)

    Example:
        WORDPRESS_SITE1_URL=https://example.com
        WORDPRESS_SITE1_USERNAME=admin
        WORDPRESS_SITE1_APP_PASSWORD=xxxx
        WORDPRESS_SITE2_URL=https://myblog.com
        WORDPRESS_SITE2_ALIAS=myblog
    """

    def __init__(self):
        """Initialize site registry."""
        self.sites: dict[str, SiteInfo] = {}  # full_id -> SiteInfo
        self.aliases: dict[str, str] = {}  # alias -> full_id
        self.alias_conflicts: dict[str, list[str]] = {}  # alias -> [full_ids that wanted it]
        self.logger = logging.getLogger("SiteRegistry")

    def discover_sites(self, plugin_types: list[str]) -> None:
        """
        Discover sites from environment variables.

        Args:
            plugin_types: List of plugin types to discover (e.g., ['wordpress'])
        """
        self.logger.info("Starting site discovery...")

        for plugin_type in plugin_types:
            self._discover_plugin_sites(plugin_type)

        self.logger.info(
            f"Discovery complete. Found {len(self.sites)} sites "
            f"with {len(self.aliases)} aliases."
        )

        # Log alias conflicts if any
        if self.alias_conflicts:
            self.logger.info("Duplicate alias conflicts detected:")
            for alias, full_ids in self.alias_conflicts.items():
                winner = self.aliases.get(alias)
                losers = [fid for fid in full_ids if fid != winner]
                self.logger.info(
                    f"  Alias '{alias}': {winner} (winner), {losers} (using full_id)"
                )

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

    def _discover_plugin_sites(self, plugin_type: str) -> None:
        """
        Discover all sites for a specific plugin type.

        Args:
            plugin_type: Type of plugin (e.g., 'wordpress')
        """
        prefix = plugin_type.upper() + "_"

        # Find all site IDs for this plugin type
        site_ids = set()
        env_pattern = re.compile(f"^{prefix}([A-Z0-9_]+?)_(.+)$")

        for env_key in os.environ.keys():
            match = env_pattern.match(env_key)
            if match:
                site_id = match.group(1).lower()
                # Skip reserved words that are not real site IDs
                if site_id not in self.RESERVED_SITE_WORDS:
                    site_ids.add(site_id)

        # Create SiteInfo for each discovered site
        for site_id in site_ids:
            try:
                config = self._load_site_config(plugin_type, site_id)
                if config:
                    alias = config.pop("alias", None)  # Extract alias if present
                    site_info = SiteInfo(plugin_type, site_id, config, alias)

                    full_id = site_info.get_full_id()
                    self.sites[full_id] = site_info

                    # Register alias with duplicate detection
                    if alias:
                        self._register_alias_safe(alias, full_id)
                        # Also register with prefix
                        prefixed_alias = f"{plugin_type}_{alias}"
                        self._register_alias_safe(prefixed_alias, full_id)

                    # Always register site_id as alias too (with safe check)
                    self._register_alias_safe(site_id, full_id)
                    self.aliases[full_id] = (
                        full_id  # full_id can reference itself (no conflict possible)
                    )

                    # Log with alias status
                    effective_alias = self._get_effective_alias(alias, full_id)
                    self.logger.info(f"Discovered site: {full_id} " f"(path: {effective_alias})")
            except Exception as e:
                self.logger.error(
                    f"Failed to load {plugin_type} site '{site_id}': {e}", exc_info=True
                )

    def _register_alias_safe(self, alias: str, full_id: str) -> bool:
        """
        Register an alias with duplicate detection.

        Args:
            alias: The alias to register
            full_id: The full_id to map the alias to

        Returns:
            True if alias was registered, False if it was a duplicate
        """
        if alias in self.aliases:
            existing_full_id = self.aliases[alias]
            if existing_full_id != full_id:
                # Duplicate alias detected
                if alias not in self.alias_conflicts:
                    self.alias_conflicts[alias] = [existing_full_id]
                self.alias_conflicts[alias].append(full_id)
                self.logger.info(
                    f"Duplicate alias '{alias}': {full_id} conflicts with {existing_full_id}. "
                    f"{full_id} will use full_id for endpoint path."
                )
                return False
        else:
            self.aliases[alias] = full_id
        return True

    def _get_effective_alias(self, alias: str | None, full_id: str) -> str:
        """
        Get the effective path suffix for a site.

        If the alias was taken by another site, returns full_id.
        Otherwise returns the alias (or full_id if no alias).

        Args:
            alias: The desired alias
            full_id: The full site ID

        Returns:
            The effective path suffix
        """
        if alias:
            # Check if this site owns the alias
            if self.aliases.get(alias) == full_id:
                return alias
            else:
                # Alias was taken, use full_id
                return full_id
        return full_id

    def get_alias_conflicts(self) -> dict[str, list[str]]:
        """
        Get all alias conflicts.

        Returns:
            Dict mapping conflicted aliases to list of full_ids that wanted them
        """
        return self.alias_conflicts.copy()

    def get_effective_path_suffix(self, full_id: str) -> str:
        """
        Get the effective path suffix for a site's endpoint.

        Uses alias if available and not conflicted, otherwise full_id.

        Args:
            full_id: The full site ID

        Returns:
            Path suffix to use in endpoint URL
        """
        site_info = self.sites.get(full_id)
        if not site_info:
            return full_id

        alias = site_info.alias
        return self._get_effective_alias(alias, full_id)

    def _load_site_config(self, plugin_type: str, site_id: str) -> dict[str, Any] | None:
        """
        Load configuration for a site from environment.

        Args:
            plugin_type: Plugin type
            site_id: Site ID

        Returns:
            Dict with configuration or None if incomplete
        """
        prefix = f"{plugin_type.upper()}_{site_id.upper()}_"
        config = {}

        # Collect all config keys for this site
        for env_key, env_value in os.environ.items():
            if env_key.startswith(prefix):
                # Extract config key (everything after prefix)
                config_key = env_key[len(prefix) :].lower()
                config[config_key] = env_value

        if not config:
            return None

        self.logger.debug(f"Loaded config for {plugin_type}/{site_id}: {list(config.keys())}")
        return config

    def get_site(self, plugin_type: str, site_identifier: str) -> SiteInfo | None:
        """
        Get site information by ID or alias.

        Args:
            plugin_type: Plugin type (e.g., 'wordpress')
            site_identifier: Site ID, alias, or full_id

        Returns:
            SiteInfo if found, None otherwise
        """
        # Try direct lookup first
        full_id = f"{plugin_type}_{site_identifier}"
        if full_id in self.sites:
            return self.sites[full_id]

        # Try alias lookup
        if site_identifier in self.aliases:
            resolved_full_id = self.aliases[site_identifier]
            return self.sites.get(resolved_full_id)

        # Try prefixed alias
        prefixed = f"{plugin_type}_{site_identifier}"
        if prefixed in self.aliases:
            resolved_full_id = self.aliases[prefixed]
            return self.sites.get(resolved_full_id)

        return None

    def get_sites_by_type(self, plugin_type: str) -> list[SiteInfo]:
        """
        Get all sites of a specific plugin type.

        Args:
            plugin_type: Plugin type to filter by

        Returns:
            List of SiteInfo objects
        """
        return [
            site_info for site_info in self.sites.values() if site_info.plugin_type == plugin_type
        ]

    def list_all_sites(self) -> list[dict[str, Any]]:
        """
        List all discovered sites.

        Returns:
            List of site info dictionaries
        """
        return [site_info.to_dict() for site_info in self.sites.values()]

    def get_site_options(self, plugin_type: str) -> list[str]:
        """
        Get available site options for a plugin type (for schema enum).

        Args:
            plugin_type: Plugin type

        Returns:
            List of valid site identifiers (IDs and aliases)
        """
        options = set()
        for site_info in self.get_sites_by_type(plugin_type):
            options.add(site_info.site_id)
            if site_info.alias and site_info.alias != site_info.site_id:
                options.add(site_info.alias)
        return sorted(options)


# Global site registry instance
_site_registry: SiteRegistry | None = None


def get_site_registry() -> SiteRegistry:
    """Get the global site registry instance."""
    global _site_registry
    if _site_registry is None:
        _site_registry = SiteRegistry()
    return _site_registry
