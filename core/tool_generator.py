"""
Tool Generator - Direct tool generation without per-site wrapper

Generates MCP tools directly from plugin specifications.
Part of Option B clean architecture refactoring.
"""

import copy
import logging
from collections.abc import Callable
from typing import Any

from core.tool_registry import ToolDefinition

logger = logging.getLogger(__name__)


# Plugin type fallback mapping - used when a plugin has no sites configured
# WooCommerce can fallback to WordPress sites (same URL, credentials)
# NOTE: Using fallback is NOT recommended in production. Always configure
# explicit WOOCOMMERCE_SITE*_... environment variables for stability.
PLUGIN_SITE_FALLBACK = {
    "woocommerce": "wordpress",  # WooCommerce can use WordPress site configs
    # Add more fallbacks as needed
}


def get_site_plugin_type_with_fallback(plugin_type: str, site_manager) -> str:
    """
    Get the site configuration plugin type for a given plugin.

    Checks if the plugin has its own sites configured first.
    If not, falls back to a related plugin type (e.g., woocommerce -> wordpress).

    WARNING: Using fallback is not recommended for production use.
    Always configure explicit environment variables for each plugin type
    to avoid issues with alias mismatches and credential problems.

    Args:
        plugin_type: The plugin type
        site_manager: SiteManager instance to check for configured sites

    Returns:
        The plugin type to use for site configuration lookup
    """
    # First check if the plugin has its own sites
    if plugin_type in site_manager.sites and site_manager.sites[plugin_type]:
        return plugin_type

    # Fallback to related plugin type if available
    fallback_type = PLUGIN_SITE_FALLBACK.get(plugin_type)
    if fallback_type and fallback_type in site_manager.sites:
        # Log a warning - fallback usage is not recommended
        logger.warning(
            f"FALLBACK: Using {fallback_type} site config for {plugin_type}. "
            f"This is NOT recommended for production. "
            f"Please configure explicit {plugin_type.upper()}_SITE*_... environment variables "
            f"to avoid potential issues with alias mismatches and credentials."
        )
        return fallback_type

    # Return original type (may have no sites)
    return plugin_type


class ToolGenerator:
    """
    Generate tools directly from plugin classes.

    No longer wraps per-site tools - generates tools directly
    from plugin specifications with site parameter routing.

    Attributes:
        site_manager: Manages site configurations
        logger: Logger instance

    Examples:
        >>> generator = ToolGenerator(site_manager)
        >>> tools = generator.generate_tools(WordPressPlugin, "wordpress")
        >>> print(f"Generated {len(tools)} tools")
    """

    def __init__(self, site_manager):
        """
        Initialize tool generator.

        Args:
            site_manager: SiteManager instance for site configuration
        """
        self.site_manager = site_manager
        self.logger = logging.getLogger("ToolGenerator")

    def generate_tools(self, plugin_class: type, plugin_type: str) -> list[ToolDefinition]:
        """
        Generate tools directly from plugin class.

        Args:
            plugin_class: Plugin class (not instance)
            plugin_type: Plugin type name (e.g., 'wordpress')

        Returns:
            List of tool definitions

        Raises:
            ValueError: If plugin_class doesn't have get_tool_specifications

        Examples:
            >>> tools = generator.generate_tools(WordPressPlugin, "wordpress")
        """
        # Verify plugin class has required method
        if not hasattr(plugin_class, "get_tool_specifications"):
            raise ValueError(
                f"Plugin class {plugin_class.__name__} must implement "
                "get_tool_specifications() static method"
            )

        # Get tool specifications from plugin
        try:
            tool_specs = plugin_class.get_tool_specifications()
        except Exception as e:
            self.logger.error(
                f"Failed to get tool specifications from {plugin_class.__name__}: {e}",
                exc_info=True,
            )
            return []

        self.logger.info(
            f"Generating tools for {plugin_type} " f"from {len(tool_specs)} specifications"
        )

        tools = []
        for spec in tool_specs:
            try:
                tool = self._create_tool_from_spec(plugin_class, plugin_type, spec)
                if tool:
                    tools.append(tool)
            except Exception as e:
                self.logger.error(
                    f"Failed to create tool from spec {spec.get('name', 'unknown')}: {e}",
                    exc_info=True,
                )

        self.logger.info(f"Generated {len(tools)} tools for {plugin_type}")
        return tools

    def _create_tool_from_spec(
        self, plugin_class: type, plugin_type: str, spec: dict[str, Any]
    ) -> ToolDefinition:
        """
        Create a tool definition from a specification.

        Args:
            plugin_class: Plugin class
            plugin_type: Plugin type name
            spec: Tool specification dictionary

        Returns:
            Tool definition

        Raises:
            ValueError: If spec is invalid

        Tool spec format:
            {
                'name': 'list_posts',
                'method_name': 'list_posts',
                'description': 'List WordPress posts',
                'schema': {...},  # Input schema (without site param)
                'scope': 'read'   # Optional, defaults to 'read'
            }
        """
        # Validate required fields
        required_fields = ["name", "method_name", "description", "schema"]
        for field in required_fields:
            if field not in spec:
                raise ValueError(f"Tool spec missing required field: {field}")

        # Extract spec fields
        action_name = spec["name"]
        method_name = spec["method_name"]
        description = spec["description"]
        schema = spec["schema"]
        scope = spec.get("scope", "read")

        # Create full tool name
        tool_name = f"{plugin_type}_{action_name}"

        # Add site parameter to schema
        enhanced_schema = self._add_site_parameter(schema, plugin_type)

        # Add [UNIFIED] prefix to description if not present
        if not description.startswith("[UNIFIED]"):
            description = f"[UNIFIED] {description}"

        # Create handler with site routing
        handler = self._create_handler(plugin_class, plugin_type, method_name)

        return ToolDefinition(
            name=tool_name,
            description=description,
            input_schema=enhanced_schema,
            handler=handler,
            required_scope=scope,
            plugin_type=plugin_type,
        )

    def _add_site_parameter(
        self, original_schema: dict[str, Any], plugin_type: str
    ) -> dict[str, Any]:
        """
        Add 'site' parameter to input schema.

        Args:
            original_schema: Original input schema
            plugin_type: Plugin type for site options

        Returns:
            Schema with site parameter added

        Examples:
            >>> schema = {'type': 'object', 'properties': {'post_id': {...}}}
            >>> enhanced = generator._add_site_parameter(schema, 'wordpress')
            >>> assert 'site' in enhanced['properties']
        """
        # Deep copy to avoid modifying original
        schema = copy.deepcopy(original_schema)

        # Ensure schema has required structure
        if "properties" not in schema:
            schema["properties"] = {}
        if "required" not in schema:
            schema["required"] = []

        # Get available sites for this plugin type
        # Use fallback if no sites configured (e.g., woocommerce -> wordpress)
        site_plugin_type = get_site_plugin_type_with_fallback(plugin_type, self.site_manager)
        site_options = self.site_manager.list_sites(site_plugin_type)

        if not site_options:
            # No sites configured - add site param anyway for future use
            site_options = []

        # Phase K.2.6: For single-site MCPs, make site parameter optional
        is_single_site = len(site_options) == 1

        if is_single_site:
            # Single site - parameter is optional with helpful description
            single_site = site_options[0]
            schema["properties"] = {
                "site": {
                    "type": "string",
                    "description": (
                        f"🔗 SINGLE SITE: Connected to '{single_site}'. "
                        f"This parameter is OPTIONAL - you can omit it or use any value."
                    ),
                    "default": single_site,
                },
                **schema["properties"],
            }
            # Don't add 'site' to required for single-site MCPs
        else:
            # Multiple sites or no sites - parameter is required
            schema["properties"] = {
                "site": {
                    "type": "string",
                    "description": (
                        f"Site ID or alias. "
                        f"Available options: {', '.join(site_options) if site_options else 'None configured'}. "
                        f"Use list_sites() to see all configured sites."
                    ),
                    **({"enum": site_options} if site_options else {}),
                },
                **schema["properties"],
            }
            # Make 'site' required for multi-site MCPs
            if "site" not in schema["required"]:
                schema["required"].insert(0, "site")

        return schema

    def _create_handler(self, plugin_class: type, plugin_type: str, method_name: str) -> Callable:
        """
        Create async handler with site routing.

        The handler:
        1. Extracts site from parameters
        2. Gets site configuration
        3. Creates plugin instance for this request
        4. Calls the specified method
        5. Returns result

        Args:
            plugin_class: Plugin class to instantiate
            plugin_type: Plugin type name
            method_name: Method name to call on plugin instance

        Returns:
            Async handler function

        Examples:
            >>> handler = generator._create_handler(
            ...     WordPressPlugin, "wordpress", "list_posts"
            ... )
            >>> result = await handler(site="site1", per_page=10)
        """

        async def unified_handler(site: str = None, **kwargs):
            """
            Unified handler that routes to the correct site plugin.

            Args:
                site: Site ID or alias (optional for single-site MCPs)
                **kwargs: Other parameters for the tool

            Returns:
                Result from plugin method

            Raises:
                ValueError: If site not found or access denied
            """
            try:
                # Get site configuration
                # Use fallback if no sites configured (e.g., woocommerce -> wordpress)
                site_plugin_type = get_site_plugin_type_with_fallback(
                    plugin_type, self.site_manager
                )

                # Phase K.2.6: Auto-detect site for single-site MCPs
                if not site:
                    available_sites = self.site_manager.list_sites(site_plugin_type)
                    if len(available_sites) == 1:
                        site = available_sites[0]
                    elif len(available_sites) == 0:
                        return "Error: No sites configured. Please check environment variables."
                    else:
                        return (
                            f"Error: Multiple sites available ({', '.join(available_sites)}). "
                            f"Please specify the 'site' parameter."
                        )

                site_config = self.site_manager.get_site_config(site_plugin_type, site)

                # SECURITY: Check if API key has access to this project
                from core.context import get_api_key_context

                api_key_info = get_api_key_context()

                if api_key_info and not api_key_info.get("is_global"):
                    # Per-project key - must match the project
                    allowed_project = api_key_info.get("project_id")

                    # Resolve the current project - always use site_id for consistency
                    # Use site_plugin_type for consistent project naming
                    current_project = f"{site_plugin_type}_{site_config.site_id}"

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
                                allowed_site_config = self.site_manager.get_site_config(
                                    allowed_plugin_type, allowed_site_identifier
                                )
                                # Normalize to plugin_type_site_id format
                                allowed_project_normalized = (
                                    f"{allowed_plugin_type}_{allowed_site_config.site_id}"
                                )
                            except ValueError:
                                # Site not found, keep original for error message
                                pass

                    if allowed_project_normalized != current_project:
                        logger.warning(
                            f"Access denied: API key for project '{allowed_project}' "
                            f"attempted to access '{current_project}'"
                        )
                        return (
                            f"Error: Access denied. This API key is restricted to project '{allowed_project}'. "
                            f"Use a global API key or create a key for '{current_project}'."
                        )

                # Create plugin instance for this request
                # Convert SiteConfig Pydantic model to dict
                # Use model_dump() for Pydantic V2, fallback to dict() for V1
                if hasattr(site_config, "model_dump"):
                    config_dict = site_config.model_dump()
                elif hasattr(site_config, "dict"):
                    config_dict = site_config.dict()
                else:
                    config_dict = site_config

                plugin_instance = plugin_class(config_dict)

                # Get the method from plugin instance
                if not hasattr(plugin_instance, method_name):
                    return (
                        f"Error: Method '{method_name}' not found in "
                        f"{plugin_class.__name__}. This is a plugin implementation error."
                    )

                method = getattr(plugin_instance, method_name)

                # Phase K.2.1: Enhanced parameter processing
                # 1. Parse JSON strings to objects (for billing, shipping, line_items, etc.)
                # 2. Filter out None and empty values
                import json as json_module

                def process_value(value):
                    """Process parameter value - parse JSON strings if needed."""
                    if value is None:
                        return None
                    if isinstance(value, str):
                        # Skip empty strings
                        if value.strip() == "":
                            return None
                        # Try to parse JSON strings
                        stripped = value.strip()
                        if (stripped.startswith("{") and stripped.endswith("}")) or (
                            stripped.startswith("[") and stripped.endswith("]")
                        ):
                            try:
                                return json_module.loads(value)
                            except json_module.JSONDecodeError:
                                # Not valid JSON, return original string
                                return value
                    return value

                filtered_kwargs = {}
                for key, value in kwargs.items():
                    processed = process_value(value)
                    if processed is not None:
                        filtered_kwargs[key] = processed

                # Call the method
                result = await method(**filtered_kwargs)
                return result

            except ValueError as e:
                # Site not found or validation error
                logger.warning(f"Validation error in {plugin_type}_{method_name}: {e}")
                return f"Error: {str(e)}"

            except Exception as e:
                # Import custom exceptions for better error handling
                from plugins.wordpress.client import AuthenticationError, ConfigurationError

                error_type = type(e).__name__

                if isinstance(e, ConfigurationError):
                    # Configuration error - likely missing env vars
                    logger.error(f"Configuration error in {plugin_type}_{method_name}: {e}")
                    return (
                        f"Configuration Error: {str(e)}\n\n"
                        f"Hint: For {plugin_type}, ensure these environment variables are set:\n"
                        f"  - {plugin_type.upper()}_SITE*_URL\n"
                        f"  - {plugin_type.upper()}_SITE*_USERNAME\n"
                        f"  - {plugin_type.upper()}_SITE*_APP_PASSWORD"
                    )

                elif isinstance(e, AuthenticationError):
                    # Authentication error - 401/403
                    logger.warning(f"Authentication error in {plugin_type}_{method_name}: {e}")
                    return f"Authentication Error: {str(e)}"

                else:
                    # Unexpected error
                    logger.error(
                        f"Error in unified handler for {plugin_type}_{method_name}: {e}",
                        exc_info=True,
                    )
                    return f"Error ({error_type}): {str(e)}"

        # Set function name for better debugging
        unified_handler.__name__ = f"{plugin_type}_{method_name}_handler"

        return unified_handler

    def generate_all_tools(self, plugin_classes: dict[str, type]) -> list[ToolDefinition]:
        """
        Generate tools for all plugin classes.

        Args:
            plugin_classes: Dict mapping plugin_type to plugin class

        Returns:
            List of all tool definitions

        Examples:
            >>> plugins = {
            ...     'wordpress': WordPressPlugin,
            ...     'gitea': GiteaPlugin
            ... }
            >>> all_tools = generator.generate_all_tools(plugins)
        """
        all_tools = []

        for plugin_type, plugin_class in plugin_classes.items():
            try:
                tools = self.generate_tools(plugin_class, plugin_type)
                all_tools.extend(tools)
            except Exception as e:
                self.logger.error(f"Failed to generate tools for {plugin_type}: {e}", exc_info=True)

        self.logger.info(
            f"Generated {len(all_tools)} total tools " f"across {len(plugin_classes)} plugin types"
        )

        return all_tools
