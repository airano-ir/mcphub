"""
Unified Tool Generator

Generates context-based tools that work across multiple sites.
Maintains backward compatibility by keeping per-site tools.

Architecture:
- Old: wordpress_site1_get_post(post_id)
- New: wordpress_get_post(site, post_id)
- Both work simultaneously!
"""

import logging
from collections.abc import Callable
from typing import Any

from core.site_registry import get_site_registry

logger = logging.getLogger(__name__)

class UnifiedToolGenerator:
    """
    Generates unified tools from per-site tool definitions.

    Takes existing plugin tools and creates context-based versions
    that accept a 'site' parameter for dynamic routing.
    """

    def __init__(self, project_manager):
        """
        Initialize unified tool generator.

        Args:
            project_manager: ProjectManager instance with discovered projects
        """
        self.project_manager = project_manager
        self.site_registry = get_site_registry()
        self.logger = logging.getLogger("UnifiedToolGenerator")

    def generate_unified_tools(self, plugin_type: str) -> list[dict[str, Any]]:
        """
        Generate unified tools for a specific plugin type.

        Args:
            plugin_type: Type of plugin (e.g., 'wordpress')

        Returns:
            List of unified tool definitions
        """
        # Get all projects of this type
        projects = self.project_manager.get_projects_by_type(plugin_type)

        if not projects:
            self.logger.warning(f"No projects found for plugin type: {plugin_type}")
            return []

        # Use the first project as a template to get tool definitions
        first_project_id = list(projects.keys())[0]
        template_plugin = projects[first_project_id]
        template_tools = template_plugin.get_tools()

        self.logger.info(
            f"Generating unified tools for {plugin_type} "
            f"from {len(template_tools)} template tools"
        )

        unified_tools = []
        seen_actions = set()

        for tool in template_tools:
            # Extract action name from per-site tool name
            # e.g., "wordpress_site1_get_post" -> "get_post"
            tool_name = tool["name"]
            parts = tool_name.split("_")

            # Skip if not in expected format
            if len(parts) < 3:
                continue

            # Extract action (everything after plugin_type_site_id_)
            # e.g., wordpress_site1_get_post -> get_post
            action = "_".join(parts[2:])

            # Skip duplicates (we only need one unified tool per action)
            if action in seen_actions:
                continue
            seen_actions.add(action)

            # Create unified tool
            unified_tool = self._create_unified_tool(
                plugin_type=plugin_type, action=action, template_tool=tool
            )

            if unified_tool:
                unified_tools.append(unified_tool)

        self.logger.info(f"Generated {len(unified_tools)} unified tools for {plugin_type}")
        return unified_tools

    def _create_unified_tool(
        self, plugin_type: str, action: str, template_tool: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Create a unified tool from a template.

        Args:
            plugin_type: Plugin type (e.g., 'wordpress')
            action: Action name (e.g., 'get_post')
            template_tool: Original per-site tool definition

        Returns:
            Unified tool definition
        """
        try:
            # Create unified tool name
            unified_name = f"{plugin_type}_{action}"

            # Get available sites for this plugin type
            site_options = self.site_registry.get_site_options(plugin_type)

            if not site_options:
                self.logger.warning(f"No sites available for {plugin_type}, skipping {action}")
                return None

            # Modify input schema to add 'site' parameter
            original_schema = template_tool.get("inputSchema", {})
            unified_schema = self._add_site_parameter(original_schema, plugin_type, site_options)

            # Update description to mention site parameter
            original_description = template_tool.get("description", "")
            unified_description = self._update_description(original_description, plugin_type)

            # Create wrapper handler
            original_handler = template_tool.get("handler")
            unified_handler = self._create_unified_handler(plugin_type, action, original_handler)

            return {
                "name": unified_name,
                "description": unified_description,
                "inputSchema": unified_schema,
                "handler": unified_handler,
            }

        except Exception as e:
            self.logger.error(
                f"Error creating unified tool for {plugin_type}_{action}: {e}", exc_info=True
            )
            return None

    def _add_site_parameter(
        self, original_schema: dict[str, Any], plugin_type: str, site_options: list[str]
    ) -> dict[str, Any]:
        """
        Add 'site' parameter to input schema.

        Args:
            original_schema: Original input schema
            plugin_type: Plugin type
            site_options: Available site IDs/aliases

        Returns:
            Modified schema with site parameter
        """
        # Deep copy to avoid modifying original
        import copy

        schema = copy.deepcopy(original_schema)

        # Ensure schema has required structure
        if "properties" not in schema:
            schema["properties"] = {}
        if "required" not in schema:
            schema["required"] = []

        # Add 'site' as first parameter
        schema["properties"] = {
            "site": {
                "type": "string",
                "description": (
                    f"Site ID or alias. Available options: {', '.join(site_options)}. "
                    f"Use list_projects() to see all configured sites."
                ),
                "enum": site_options,
            },
            **schema["properties"],
        }

        # Make 'site' required
        if "site" not in schema["required"]:
            schema["required"].insert(0, "site")

        return schema

    def _update_description(self, original_description: str, plugin_type: str) -> str:
        """
        Update tool description to mention unified context.

        Args:
            original_description: Original description
            plugin_type: Plugin type

        Returns:
            Updated description
        """
        # Remove site-specific mentions (e.g., "from site1", "in site2")
        import re

        cleaned = re.sub(
            r"\b(?:from|in|for)\s+site\d+\b", "", original_description, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"\bsite\d+\b", f"the specified {plugin_type} site", cleaned, flags=re.IGNORECASE
        )

        # Add unified context note
        prefix = "[UNIFIED] "
        if not cleaned.startswith(prefix):
            cleaned = prefix + cleaned

        return cleaned.strip()

    def _create_unified_handler(
        self, plugin_type: str, action: str, original_handler: Callable | None
    ) -> Callable:
        """
        Create a unified handler that routes to the correct site.

        Args:
            plugin_type: Plugin type
            action: Action name
            original_handler: Original handler (not used, we call plugin method directly)

        Returns:
            Async handler function
        """

        async def unified_handler(site: str, **kwargs):
            """
            Unified handler that routes to the correct site plugin.

            Args:
                site: Site ID or alias
                **kwargs: Other parameters for the tool
            """
            try:
                # Get site info from registry
                site_info = self.site_registry.get_site(plugin_type, site)

                if not site_info:
                    available = self.site_registry.get_site_options(plugin_type)
                    return (
                        f"Error: Site '{site}' not found for {plugin_type}. "
                        f"Available sites: {', '.join(available)}"
                    )

                # Get the plugin instance
                full_id = site_info.get_full_id()

                # SECURITY: Check if API key has access to this project
                from core.context import get_api_key_context

                api_key_info = get_api_key_context()

                if api_key_info and not api_key_info.get("is_global"):
                    # Per-project key - must match the project
                    allowed_project = api_key_info.get("project_id")

                    # Resolve allowed_project to normalize alias vs site_id
                    # API key might have been created with alias (wordpress_myblog)
                    # or site_id (wordpress_site1)
                    allowed_project_normalized = allowed_project
                    if allowed_project and "_" in allowed_project:
                        # Extract plugin type and site identifier from allowed_project
                        allowed_parts = allowed_project.split("_", 1)
                        if len(allowed_parts) == 2:
                            allowed_plugin_type, allowed_site_identifier = allowed_parts
                            # Try to resolve the site identifier to site_id
                            try:
                                allowed_site_info = self.site_registry.get_site(
                                    allowed_plugin_type, allowed_site_identifier
                                )
                                if allowed_site_info:
                                    # Normalize to plugin_type_site_id format
                                    allowed_project_normalized = allowed_site_info.get_full_id()
                            except (ValueError, Exception):
                                # Site not found, keep original for error message
                                pass

                    if allowed_project_normalized != full_id:
                        logger.warning(
                            f"Access denied: API key for project '{allowed_project}' "
                            f"attempted to access '{full_id}'"
                        )
                        return (
                            f"Error: Access denied. This API key is restricted to project '{allowed_project}'. "
                            f"Use a global API key or create a key for '{full_id}'."
                        )

                plugin = self.project_manager.get_project(full_id)

                if not plugin:
                    return f"Error: Plugin instance not found for {full_id}"

                # Find the original handler method in the plugin
                # The original per-site tool name was: {plugin_type}_{site_id}_{action}
                original_tool_name = f"{plugin_type}_{site_info.site_id}_{action}"

                # Get all tools from plugin and find the matching handler
                tools = plugin.get_tools()
                handler = None

                for tool in tools:
                    if tool["name"] == original_tool_name:
                        handler = tool.get("handler")
                        break

                if not handler:
                    return (
                        f"Error: Handler not found for {original_tool_name}. "
                        f"This may be a plugin implementation issue."
                    )

                # Filter out None values from kwargs to avoid validation errors
                # WordPress API doesn't accept None values in query parameters
                filtered_kwargs = {key: value for key, value in kwargs.items() if value is not None}

                # Call the handler with filtered kwargs
                result = await handler(**filtered_kwargs)
                return result

            except Exception as e:
                logger.error(
                    f"Error in unified handler for {plugin_type}_{action}: {e}", exc_info=True
                )
                return f"Error: {str(e)}"

        return unified_handler

    def generate_all_unified_tools(self) -> list[dict[str, Any]]:
        """
        Generate unified tools for all registered plugin types.

        Returns:
            List of all unified tool definitions
        """
        all_tools = []

        # Get all plugin types from registry
        from plugins import registry

        plugin_types = registry.get_registered_types()

        for plugin_type in plugin_types:
            tools = self.generate_unified_tools(plugin_type)
            all_tools.extend(tools)

        self.logger.info(
            f"Generated {len(all_tools)} total unified tools "
            f"across {len(plugin_types)} plugin types"
        )

        return all_tools
