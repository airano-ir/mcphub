"""
Project Manager

Discovers and manages project instances from environment variables.
Handles plugin lifecycle and tool registration.
"""

import logging
import os
import re
from typing import Any

from plugins import BasePlugin, registry

logger = logging.getLogger(__name__)


class ProjectManager:
    """
    Manage multiple project instances.

    Projects are discovered from environment variables:
    - {PLUGIN_TYPE}_{PROJECT_ID}_{CONFIG_KEY}

    Example:
        WORDPRESS_SITE1_URL=https://example.com
        WORDPRESS_SITE1_USERNAME=admin
        WORDPRESS_SITE1_APP_PASSWORD=xxxx
        WORDPRESS_SITE2_URL=https://other.com
        ...
    """

    def __init__(self):
        """Initialize project manager."""
        self.projects: dict[str, BasePlugin] = {}
        self.logger = logging.getLogger("ProjectManager")

    def discover_projects(self) -> None:
        """
        Discover projects from environment variables.

        Scans environment for project configurations and creates
        plugin instances.
        """
        self.logger.info("Starting project discovery...")

        # Get all registered plugin types
        plugin_types = registry.get_registered_types()

        for plugin_type in plugin_types:
            self._discover_plugin_type(plugin_type)

        self.logger.info(f"Discovery complete. Found {len(self.projects)} projects.")

    def _discover_plugin_type(self, plugin_type: str) -> None:
        """
        Discover all projects of a specific plugin type.

        Args:
            plugin_type: Type of plugin (e.g., 'wordpress')
        """
        prefix = plugin_type.upper() + "_"

        # Find all project IDs for this plugin type
        project_ids = set()
        env_pattern = re.compile(f"^{prefix}([A-Z0-9_]+?)_(.+)$")

        for env_key in os.environ.keys():
            match = env_pattern.match(env_key)
            if match:
                project_id = match.group(1).lower()
                project_ids.add(project_id)

        # Create plugin instance for each project
        for project_id in project_ids:
            try:
                config = self._load_project_config(plugin_type, project_id)
                if config:
                    self._create_project_instance(plugin_type, project_id, config)
            except Exception as e:
                self.logger.error(
                    f"Failed to create {plugin_type} project '{project_id}': {e}", exc_info=True
                )

    def _load_project_config(self, plugin_type: str, project_id: str) -> dict[str, Any] | None:
        """
        Load configuration for a project from environment.

        Args:
            plugin_type: Plugin type
            project_id: Project ID

        Returns:
            Dict with configuration or None if incomplete
        """
        prefix = f"{plugin_type.upper()}_{project_id.upper()}_"
        config = {}

        # Collect all config keys for this project
        for env_key, env_value in os.environ.items():
            if env_key.startswith(prefix):
                # Extract config key (everything after prefix)
                config_key = env_key[len(prefix) :].lower()
                config[config_key] = env_value

        if not config:
            return None

        self.logger.debug(f"Loaded config for {plugin_type}/{project_id}: {list(config.keys())}")
        return config

    def _create_project_instance(
        self, plugin_type: str, project_id: str, config: dict[str, Any]
    ) -> None:
        """
        Create a plugin instance for a project.

        Args:
            plugin_type: Plugin type
            project_id: Project ID
            config: Project configuration
        """
        try:
            # Create plugin instance
            plugin = registry.create_instance(plugin_type, project_id, config)

            # Store with full identifier
            full_id = f"{plugin_type}_{project_id}"
            self.projects[full_id] = plugin

            self.logger.info(f"Created project: {full_id}")

        except Exception as e:
            raise Exception(f"Failed to instantiate {plugin_type}/{project_id}: {e}")

    def get_project(self, full_id: str) -> BasePlugin | None:
        """
        Get a project plugin instance.

        Args:
            full_id: Full project identifier (plugin_type_project_id)

        Returns:
            Plugin instance or None
        """
        return self.projects.get(full_id)

    def get_all_projects(self) -> dict[str, BasePlugin]:
        """Get all project instances."""
        return self.projects.copy()

    def get_projects_by_type(self, plugin_type: str) -> dict[str, BasePlugin]:
        """
        Get all projects of a specific type.

        Args:
            plugin_type: Plugin type to filter by

        Returns:
            Dict of project_id -> plugin
        """
        prefix = plugin_type + "_"
        return {
            full_id: plugin
            for full_id, plugin in self.projects.items()
            if full_id.startswith(prefix)
        }

    def get_all_tools(self) -> list[dict[str, Any]]:
        """
        Get all MCP tools from all projects.

        Returns:
            List of tool definitions
        """
        all_tools = []

        for full_id, plugin in self.projects.items():
            try:
                tools = plugin.get_tools()
                all_tools.extend(tools)
                self.logger.debug(f"Loaded {len(tools)} tools from {full_id}")
            except Exception as e:
                self.logger.error(f"Error loading tools from {full_id}: {e}", exc_info=True)

        self.logger.debug(f"Total tools loaded: {len(all_tools)}")
        return all_tools

    async def check_all_health(self) -> dict[str, dict[str, Any]]:
        """
        Check health of all projects.

        Returns:
            Dict mapping project ID to health status
        """
        health_results = {}

        for full_id, plugin in self.projects.items():
            try:
                health = await plugin.health_check()
                health_results[full_id] = health
            except Exception as e:
                health_results[full_id] = {
                    "healthy": False,
                    "message": f"Health check failed: {str(e)}",
                }

        return health_results

    def get_project_info(self, full_id: str) -> dict[str, Any] | None:
        """
        Get information about a specific project.

        Args:
            full_id: Full project identifier

        Returns:
            Project info dict or None
        """
        plugin = self.get_project(full_id)
        if plugin:
            return plugin.get_project_info()
        return None

    def list_projects(self) -> list[dict[str, Any]]:
        """
        List all projects with basic information.

        Returns:
            List of project info dicts
        """
        return [
            {"id": full_id, "type": plugin.get_plugin_name(), "project_id": plugin.project_id}
            for full_id, plugin in self.projects.items()
        ]


# Global project manager instance
_project_manager: ProjectManager | None = None


def get_project_manager() -> ProjectManager:
    """Get the global project manager instance."""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
        _project_manager.discover_projects()
    return _project_manager
