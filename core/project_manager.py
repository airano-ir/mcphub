"""
Project Manager (Legacy)

Retained for backward compatibility with HealthMonitor.
Sites are now managed via the web dashboard (DB-based).
"""

import logging
from typing import Any

from plugins import BasePlugin

logger = logging.getLogger(__name__)


class ProjectManager:
    """
    Legacy project manager — retained for HealthMonitor compatibility.

    Sites are now managed via the web dashboard and stored in SQLite.
    """

    def __init__(self):
        """Initialize project manager."""
        self.projects: dict[str, BasePlugin] = {}
        self.logger = logging.getLogger("ProjectManager")

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
    return _project_manager
