"""
Endpoint Configuration Module

Defines configurations for different MCP endpoints.
Each endpoint has specific plugin types, scopes, and access requirements.
"""

from dataclasses import dataclass, field
from enum import Enum

class EndpointType(Enum):
    """Types of MCP endpoints"""

    ADMIN = "admin"
    SYSTEM = "system"  # Phase X.3 - System tools only
    WORDPRESS = "wordpress"
    WOOCOMMERCE = "woocommerce"
    WORDPRESS_ADVANCED = "wordpress_advanced"
    GITEA = "gitea"
    N8N = "n8n"
    SUPABASE = "supabase"  # Phase G
    OPENPANEL = "openpanel"  # Phase H
    APPWRITE = "appwrite"  # Phase I
    DIRECTUS = "directus"  # Phase J
    PROJECT = "project"  # Dynamic per-project endpoint
    CUSTOM = "custom"

@dataclass
class EndpointConfig:
    """
    Configuration for a single MCP endpoint.

    Attributes:
        path: URL mount path for this endpoint (e.g., "/wordpress" → /wordpress/mcp)
        name: Display name for the endpoint
        description: Human-readable description
        endpoint_type: Type of endpoint (admin, wordpress, etc.)
        plugin_types: List of plugin types to include
        require_master_key: Whether Master API Key is required
        allowed_scopes: Allowed API key scopes (empty = all)
        tool_whitelist: Specific tools to include (None = all from plugins)
        tool_blacklist: Specific tools to exclude
        site_filter: Filter to specific site (for project endpoints)
        max_tools: Maximum number of tools (for safety)
    """

    path: str
    name: str
    description: str
    endpoint_type: EndpointType
    plugin_types: list[str] = field(default_factory=list)
    require_master_key: bool = False
    allowed_scopes: set[str] = field(default_factory=set)
    tool_whitelist: set[str] | None = None
    tool_blacklist: set[str] = field(default_factory=set)
    site_filter: str | None = None
    max_tools: int = 200

    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.path.startswith("/"):
            raise ValueError(f"Endpoint path must start with '/': {self.path}")

        if self.tool_whitelist and self.tool_blacklist:
            overlap = self.tool_whitelist & self.tool_blacklist
            if overlap:
                raise ValueError(f"Tools cannot be in both whitelist and blacklist: {overlap}")

    def allows_plugin(self, plugin_type: str) -> bool:
        """Check if this endpoint allows a specific plugin type"""
        if not self.plugin_types:
            return True  # Empty list = all plugins
        return plugin_type in self.plugin_types

    def allows_tool(self, tool_name: str) -> bool:
        """Check if this endpoint allows a specific tool"""
        # Check blacklist first
        if tool_name in self.tool_blacklist:
            return False

        # If whitelist exists, tool must be in it
        if self.tool_whitelist is not None:
            return tool_name in self.tool_whitelist

        return True

    def allows_scope(self, scope: str) -> bool:
        """Check if this endpoint allows a specific API key scope"""
        if not self.allowed_scopes:
            return True  # Empty set = all scopes
        return scope in self.allowed_scopes

# Predefined endpoint configurations
ENDPOINT_CONFIGS = {
    # Admin endpoint - all tools, requires Master API Key
    # Mounted at "/" → /mcp (FastMCP adds /mcp automatically)
    EndpointType.ADMIN: EndpointConfig(
        path="/",
        name="Coolify Admin",
        description="Full administrative access to all tools and plugins",
        endpoint_type=EndpointType.ADMIN,
        plugin_types=[],  # Empty = all plugins
        require_master_key=True,
        allowed_scopes={"admin"},
        max_tools=400,
    ),
    # System endpoint - system tools only (17 tools) - Phase X.3
    # For API key management, OAuth, rate limiting without loading all plugins
    EndpointType.SYSTEM: EndpointConfig(
        path="/system",
        name="System Manager",
        description="System management tools (API keys, OAuth, health, rate limiting)",
        endpoint_type=EndpointType.SYSTEM,
        plugin_types=["system"],  # Only system tools
        require_master_key=True,
        allowed_scopes={"admin"},
        # Whitelist only system tools
        tool_whitelist={
            # API Key Management (6)
            "manage_api_keys_create",
            "manage_api_keys_list",
            "manage_api_keys_get_info",
            "manage_api_keys_revoke",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            # Health & Status (4)
            "list_projects",
            "get_endpoints",
            "get_system_info",
            "get_audit_log",
            # OAuth Management (4)
            "oauth_register_client",
            "oauth_list_clients",
            "oauth_revoke_client",
            "oauth_get_client_info",
            # Rate Limiting (3)
            "get_rate_limit_stats",
            "reset_rate_limit",
            "set_rate_limit_config",
        },
        max_tools=20,
    ),
    # WordPress endpoint - core WordPress tools only (64 tools)
    EndpointType.WORDPRESS: EndpointConfig(
        path="/wordpress",
        name="WordPress Manager",
        description="WordPress content management tools (posts, pages, media, SEO, menus)",
        endpoint_type=EndpointType.WORDPRESS,
        plugin_types=["wordpress"],
        require_master_key=False,
        allowed_scopes={"read", "write", "admin"},
        # Blacklist system and admin tools
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
        },
        max_tools=70,
    ),
    # WooCommerce endpoint - e-commerce tools (28 tools)
    EndpointType.WOOCOMMERCE: EndpointConfig(
        path="/woocommerce",
        name="WooCommerce Manager",
        description="WooCommerce e-commerce tools (products, orders, customers, coupons, reports)",
        endpoint_type=EndpointType.WOOCOMMERCE,
        plugin_types=["woocommerce"],
        require_master_key=False,
        allowed_scopes={"read", "write", "admin"},
        # Blacklist system and admin tools
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
        },
        max_tools=35,
    ),
    # WordPress Advanced endpoint - advanced operations
    EndpointType.WORDPRESS_ADVANCED: EndpointConfig(
        path="/wordpress-advanced",
        name="WordPress Advanced",
        description="WordPress advanced operations (database, bulk, system)",
        endpoint_type=EndpointType.WORDPRESS_ADVANCED,
        plugin_types=["wordpress_advanced"],
        require_master_key=False,
        allowed_scopes={"admin"},  # Admin scope required
        max_tools=30,
    ),
    # Gitea endpoint - Git repository management
    EndpointType.GITEA: EndpointConfig(
        path="/gitea",
        name="Gitea Manager",
        description="Git repository management tools (repos, issues, PRs)",
        endpoint_type=EndpointType.GITEA,
        plugin_types=["gitea"],
        require_master_key=False,
        allowed_scopes={"read", "write", "admin"},
        # Blacklist system and admin tools
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
        },
        max_tools=60,
    ),
    # n8n endpoint - Workflow automation management (60 tools)
    EndpointType.N8N: EndpointConfig(
        path="/n8n",
        name="n8n Automation",
        description="Workflow automation management (workflows, executions, credentials, tags)",
        endpoint_type=EndpointType.N8N,
        plugin_types=["n8n"],
        require_master_key=False,
        allowed_scopes={"read", "write", "admin"},
        # Blacklist system and admin tools
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
        },
        max_tools=70,
    ),
    # Supabase endpoint - Self-Hosted management (70 tools) - Phase G
    EndpointType.SUPABASE: EndpointConfig(
        path="/supabase",
        name="Supabase Manager",
        description="Supabase Self-Hosted management (database, auth, storage, functions, admin)",
        endpoint_type=EndpointType.SUPABASE,
        plugin_types=["supabase"],
        require_master_key=False,
        allowed_scopes={"read", "write", "admin"},
        # Blacklist system and admin tools
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
        },
        max_tools=80,
    ),
    # OpenPanel endpoint - Product Analytics (73 tools) - Phase H
    EndpointType.OPENPANEL: EndpointConfig(
        path="/openpanel",
        name="OpenPanel Analytics",
        description="OpenPanel product analytics management (events, export, funnels, dashboards)",
        endpoint_type=EndpointType.OPENPANEL,
        plugin_types=["openpanel"],
        require_master_key=False,
        allowed_scopes={"read", "write", "admin"},
        # Blacklist system and admin tools
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
        },
        max_tools=80,
    ),
    # Appwrite endpoint - Backend-as-a-Service (100 tools) - Phase I
    EndpointType.APPWRITE: EndpointConfig(
        path="/appwrite",
        name="Appwrite Manager",
        description="Appwrite Self-Hosted management (databases, documents, users, teams, storage, functions, messaging)",
        endpoint_type=EndpointType.APPWRITE,
        plugin_types=["appwrite"],
        require_master_key=False,
        allowed_scopes={"read", "write", "admin"},
        # Blacklist system and admin tools
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
        },
        max_tools=110,
    ),
    # Directus endpoint - Headless CMS (100 tools) - Phase J
    EndpointType.DIRECTUS: EndpointConfig(
        path="/directus",
        name="Directus CMS",
        description="Directus Self-Hosted CMS management (items, collections, files, users, roles, flows, dashboards)",
        endpoint_type=EndpointType.DIRECTUS,
        plugin_types=["directus"],
        require_master_key=False,
        allowed_scopes={"read", "write", "admin"},
        # Blacklist system and admin tools
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
        },
        max_tools=110,
    ),
}

def get_endpoint_config(endpoint_type: EndpointType) -> EndpointConfig:
    """Get configuration for a specific endpoint type"""
    if endpoint_type not in ENDPOINT_CONFIGS:
        raise ValueError(f"Unknown endpoint type: {endpoint_type}")
    return ENDPOINT_CONFIGS[endpoint_type]

def create_project_endpoint_config(
    project_id: str, plugin_type: str, site_alias: str | None = None
) -> EndpointConfig:
    """
    Create a dynamic endpoint configuration for a specific project.

    Args:
        project_id: Full project ID (e.g., "wordpress_site4")
        plugin_type: Plugin type (e.g., "wordpress")
        site_alias: Optional site alias for the path

    Returns:
        EndpointConfig for the project-specific endpoint
    """
    path_suffix = site_alias or project_id

    # FastMCP adds /mcp automatically, so /project/xxx → /project/xxx/mcp
    return EndpointConfig(
        path=f"/project/{path_suffix}",
        name=f"Project: {project_id}",
        description=f"Tools for project {project_id}",
        endpoint_type=EndpointType.PROJECT,
        plugin_types=[plugin_type],
        require_master_key=False,
        site_filter=project_id,
        # Blacklist admin tools for project endpoints
        tool_blacklist={
            "manage_api_keys_create",
            "manage_api_keys_delete",
            "manage_api_keys_rotate",
            "oauth_register_client",
            "oauth_revoke_client",
            "list_projects",  # Only show own project
            "oauth_list_clients",
        },
        max_tools=120,
    )
