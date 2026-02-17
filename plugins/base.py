"""
Base Plugin Interface

All project plugins must inherit from this base class.
This ensures consistency across different project types.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """
    Base class for all project plugins.

    Each plugin represents a specific project type (WordPress, Supabase, etc.)
    and provides MCP tools for managing that project.
    """

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize plugin with project configuration.

        **Option B Architecture (New)**:
            plugin = WordPressPlugin(config)
            # project_id extracted from config or generated

        **Legacy Architecture**:
            plugin = WordPressPlugin(config, project_id="wordpress_site1")
            # Explicit project_id

        Args:
            config: Project-specific configuration (URLs, credentials, etc.)
            project_id: Optional unique identifier (auto-generated if not provided)
        """
        # Auto-generate project_id if not provided (Option B)
        if project_id is None:
            # Generate from class name + config
            class_name = self.__class__.__name__.lower().replace("plugin", "")
            site_id = config.get("site_id", config.get("url", "unknown"))
            # Simple hash for unique ID
            import hashlib

            if isinstance(site_id, str):
                hash_suffix = hashlib.md5(site_id.encode()).hexdigest()[:8]
                project_id = f"{class_name}_{hash_suffix}"
            else:
                import time

                project_id = f"{class_name}_{int(time.time())}"

        self.project_id = project_id
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{project_id}")

        # Validate required configuration
        self._validate_config()

        self.logger.info(f"Initialized plugin for project: {project_id}")

    @abstractmethod
    def get_plugin_name(self) -> str:
        """
        Return the plugin type name (e.g., 'wordpress', 'supabase').

        Returns:
            str: Plugin type identifier
        """
        pass

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return tool specifications for Option B architecture (ToolGenerator).

        This is a STATIC method that returns tool specifications without
        needing a plugin instance. ToolGenerator uses these specifications
        to create unified tools with site parameter routing.

        Each specification should contain:
        - name: Tool name (without site prefix)
        - method_name: Method to call on plugin instance
        - description: What the tool does
        - schema: JSON Schema for input validation (without site parameter)
        - scope: Required scope (read, write, admin)

        Example:
            [
                {
                    "name": "list_posts",
                    "method_name": "list_posts",
                    "description": "List WordPress posts",
                    "schema": {...},
                    "scope": "read"
                }
            ]

        Returns:
            List[Dict]: List of tool specifications for ToolGenerator

        Note:
            Override this in subclasses for Option B architecture.
            If not implemented, returns empty list (legacy plugins).
        """
        return []

    def get_tools(self) -> list[dict[str, Any]]:
        """
        Return list of MCP tools provided by this plugin (LEGACY).

        **DEPRECATED in Option B Architecture**
        This method is kept for backward compatibility with legacy per-site
        tool architecture. New plugins should implement get_tool_specifications()
        instead, which is used by ToolGenerator for unified tools.

        Legacy per-site tools format:
        - name: Tool name (prefixed with plugin type and project_id)
        - description: What the tool does
        - inputSchema: JSON Schema for input validation
        - handler: Async function that implements the tool

        Returns:
            List[Dict]: List of tool definitions (empty for Option B plugins)

        Note:
            Option B plugins should return [] here as tools are registered
            via get_tool_specifications() + ToolGenerator instead.
        """
        return []

    def _validate_config(self) -> None:
        """
        Validate that required configuration keys are present.
        Override in subclasses to add specific validation.
        """
        required_keys = self.get_required_config_keys()
        missing_keys = [key for key in required_keys if key not in self.config]

        if missing_keys:
            raise ValueError(
                f"Missing required configuration keys for {self.project_id}: "
                f"{', '.join(missing_keys)}"
            )

    def get_required_config_keys(self) -> list[str]:
        """
        Return list of required configuration keys.
        Override in subclasses.

        Returns:
            List[str]: Required config keys
        """
        return []

    async def health_check(self) -> dict[str, Any]:
        """
        Check if the project is accessible and healthy.
        Override in subclasses to implement specific health checks.

        Returns:
            Dict with 'healthy' (bool) and 'message' (str) keys
        """
        return {"healthy": True, "message": "Health check not implemented for this plugin"}

    def get_project_info(self) -> dict[str, Any]:
        """
        Return basic information about this project instance.

        Returns:
            Dict with project metadata
        """
        return {
            "project_id": self.project_id,
            "plugin_type": self.get_plugin_name(),
            "config_keys": list(self.config.keys()),
        }

    def _create_tool_name(self, action: str) -> str:
        """
        Create a standardized tool name for per-site tools.

        FORMAT: {plugin_type}_{site_id}_{action}
        Example: wordpress_site1_list_posts

        This is used for backward-compatible per-site tools.
        Unified tools (wordpress_list_posts) are created separately by UnifiedToolGenerator.

        Args:
            action: The action this tool performs

        Returns:
            str: Formatted tool name with project_id for per-site tools
        """
        # Extract just the site_id from project_id (e.g., "site1" from "wordpress_site1")
        # project_id format is {plugin_type}_{site_id}
        site_id = self.project_id.replace(f"{self.get_plugin_name()}_", "")
        return f"{self.get_plugin_name()}_{site_id}_{action}"

    def _format_error_response(self, error: Exception, action: str) -> str:
        """
        Format an error into a user-friendly message.

        Args:
            error: The exception that occurred
            action: The action that was being performed

        Returns:
            str: Formatted error message
        """
        error_msg = f"Error performing {action} on {self.project_id}: {str(error)}"
        self.logger.error(error_msg, exc_info=True)
        return error_msg

    def _format_success_response(self, data: Any, action: str) -> str:
        """
        Format a successful response.

        Args:
            data: The data to return
            action: The action that was performed

        Returns:
            str: Formatted success message
        """
        if isinstance(data, (dict, list)):
            import json

            return json.dumps(data, indent=2, ensure_ascii=False)
        return str(data)


class PluginRegistry:
    """
    Registry for managing available plugin types.
    """

    def __init__(self):
        self._plugin_classes: dict[str, type] = {}
        self.logger = logging.getLogger("PluginRegistry")

    def register(self, plugin_type: str, plugin_class: type) -> None:
        """
        Register a plugin class.

        Args:
            plugin_type: Type identifier (e.g., 'wordpress')
            plugin_class: Plugin class (must inherit from BasePlugin)
        """
        if not issubclass(plugin_class, BasePlugin):
            raise TypeError(f"{plugin_class} must inherit from BasePlugin")

        self._plugin_classes[plugin_type] = plugin_class
        self.logger.info(f"Registered plugin type: {plugin_type}")

    def create_instance(
        self, plugin_type: str, project_id: str, config: dict[str, Any]
    ) -> BasePlugin:
        """
        Create a plugin instance.

        **Option B Compatible**: Uses new BasePlugin signature (config, project_id)

        Args:
            plugin_type: Type of plugin to create
            project_id: Unique project identifier
            config: Project configuration

        Returns:
            BasePlugin: Instantiated plugin

        Raises:
            KeyError: If plugin_type is not registered
        """
        if plugin_type not in self._plugin_classes:
            raise KeyError(f"Unknown plugin type: {plugin_type}")

        plugin_class = self._plugin_classes[plugin_type]
        # Option B signature: config first, project_id optional
        return plugin_class(config, project_id=project_id)

    def get_registered_types(self) -> list[str]:
        """Get list of registered plugin types."""
        return list(self._plugin_classes.keys())

    def is_registered(self, plugin_type: str) -> bool:
        """Check if a plugin type is registered."""
        return plugin_type in self._plugin_classes
